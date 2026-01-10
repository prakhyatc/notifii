locals {
  name = "${var.project}-${var.env}-${var.service_name}"

  common_tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Service     = var.service_name
  }

  log_group_name = "/ecs/${var.project}-${var.service_name}"
}

############################
# CloudWatch Log Group
############################
resource "aws_cloudwatch_log_group" "this" {
  name              = local.log_group_name
  retention_in_days = 14

  tags = merge(local.common_tags, {
    Name = local.log_group_name
  })
}

############################
# Security Groups
############################

# ALB SG: public inbound 80/443
resource "aws_security_group" "alb" {
  name        = "${local.name}-alb-sg"
  description = "ALB security group"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Keep 443 open now; you can add ACM + HTTPS listener later
  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name}-alb-sg" })
}

# Service SG: allow inbound ONLY from ALB SG on container_port
resource "aws_security_group" "service" {
  name        = "${local.name}-svc-sg"
  description = "Service security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "From ALB to container port"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound (needed for logs, ecr pulls via NAT, etc.)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name}-svc-sg" })
}

############################
# ALB + Target Group + Listener
############################
resource "aws_lb" "this" {
  name               = substr(replace("${local.name}-alb", "_", "-"), 0, 32)
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  tags = merge(local.common_tags, { Name = "${local.name}-alb" })
}

resource "aws_lb_target_group" "this" {
  name        = substr(replace("${local.name}-tg", "_", "-"), 0, 32)
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = merge(local.common_tags, { Name = "${local.name}-tg" })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}

############################
# ECS Cluster
############################
resource "aws_ecs_cluster" "this" {
  name = "${var.project}-${var.env}-cluster"

  tags = merge(local.common_tags, { Name = "${var.project}-${var.env}-cluster" })
}

############################
# ECS Task Definition (Fargate)
############################
resource "aws_ecs_task_definition" "this" {
  family                   = "${local.name}-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)

  execution_role_arn = var.task_execution_role_arn
  task_role_arn      = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = var.service_name
      image     = var.container_image
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "APP_ENV", value = var.env },
        { name = "AWS_REGION", value = data.aws_region.current.name },
        { name = "NOTIFII_QUEUE_URL", value = var.notifii_queue_url }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }

      healthCheck = {
        command = [
          "CMD-SHELL",
          "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()\" || exit 1"
        ]
        interval    = 10
        timeout     = 5
        retries     = 5
        startPeriod = 30
      }
    }
  ])

  tags = merge(local.common_tags, { Name = "${local.name}-taskdef" })
}

data "aws_region" "current" {}

############################
# ECS Service (private subnets)
############################
resource "aws_ecs_service" "this" {
  name            = "${local.name}-service"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = var.service_name
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]

  tags = merge(local.common_tags, { Name = "${local.name}-service" })
}