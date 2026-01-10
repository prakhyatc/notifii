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

data "aws_region" "current" {}

resource "aws_cloudwatch_log_group" "this" {
  name              = local.log_group_name
  retention_in_days = 14
  tags              = merge(local.common_tags, { Name = local.log_group_name })
}

resource "aws_security_group" "worker" {
  name        = "${local.name}-sg"
  description = "Worker security group (egress only)"
  vpc_id      = var.vpc_id

  egress {
    description = "All outbound (NAT for SQS/Logs/ECR)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name}-sg" })
}

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

      environment = [
        { name = "APP_ENV", value = var.env },
        { name = "AWS_REGION", value = data.aws_region.current.name },
        { name = "NOTIFII_QUEUE_URL", value = var.notifii_queue_url },
        { name = "SERVICE_NAME", value = var.service_name }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = merge(local.common_tags, { Name = "${local.name}-taskdef" })
}

resource "aws_ecs_service" "this" {
  name            = "${local.name}-service"
  cluster         = "${var.project}-${var.env}-cluster" # uses your existing cluster naming
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = false
  }

  tags = merge(local.common_tags, { Name = "${local.name}-service" })
}
