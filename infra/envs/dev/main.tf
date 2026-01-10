##################################################
# Modules
##################################################

# ECR repo for notification API
module "ecr_notification_api" {
  source = "../../modules/ecr"

  project         = var.project
  env             = var.env
  repository_name = "notifii-notification-api"
}

# ECR repo for email worker
module "ecr_email_worker" {
  source = "../../modules/ecr"

  project         = var.project
  env             = var.env
  repository_name = "notifii-email-worker"
}

# Network module (VPC, subnets)
module "network" {
  source = "../../modules/network"

  project = var.project
  env     = var.env

  vpc_cidr = "10.10.0.0/16"
  az_count = 2

  public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24"]
  private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24"]
}

# IAM roles for ECS tasks
module "iam" {
  source = "../../modules/iam"

  project = var.project
  env     = var.env

  task_role_policy_json = null # week 1–2 placeholder
}

# SQS queue for notifications
module "sqs_notifications" {
  source = "../../modules/sqs"

  name = "notifii-notifications"
  env  = "dev"

  max_receive_count          = 5
  visibility_timeout_seconds = 30
  message_retention_seconds  = 345600
}

##################################################
# IAM Policies and Attachments
##################################################

# Policy: Notification API can send messages to SQS
resource "aws_iam_policy" "notification_api_sqs_send" {
  name        = "${var.project}-${var.env}-notification-api-sqs-send"
  description = "Allow notification API to send messages to SQS"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = module.sqs_notifications.queue_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "notification_api_sqs_send_attach" {
  role       = module.iam.task_role_name
  policy_arn = aws_iam_policy.notification_api_sqs_send.arn
}

# Policy: Email worker can consume messages from SQS
resource "aws_iam_policy" "email_worker_sqs_consume" {
  name        = "${var.project}-${var.env}-email-worker-sqs-consume"
  description = "Allow email-worker to consume messages from SQS."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = module.sqs_notifications.queue_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "email_worker_sqs_consume_attach" {
  role       = module.iam.task_role_name
  policy_arn = aws_iam_policy.email_worker_sqs_consume.arn
}

##################################################
# ECS Services
##################################################

module "ecs_notification_api" {
  source = "../../modules/ecs_service"

  project = var.project
  env     = var.env

  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids

  service_name    = "notification-api"
  container_image = "${module.ecr_notification_api.repo_url}:dev"
  container_port  = 8000
  cpu             = 256
  memory          = 512
  desired_count   = 1

  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn           = module.iam.task_role_arn

  notifii_queue_url = module.sqs_notifications.queue_url
}
# ECS service for email worker
module "ecs_email_worker" {
  source = "../../modules/ecs_worker"

  project = var.project
  env     = var.env

  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids

  service_name    = "email-worker"
  container_image = "${module.ecr_email_worker.repo_url}:dev"

  cpu           = 256
  memory        = 512
  desired_count = 1

  notifii_queue_url = module.sqs_notifications.queue_url

  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn           = module.iam.task_role_arn
}
locals {
  notifications_queue_name  = element(reverse(split("/", module.sqs_notifications.queue_url)), 0)
  email_worker_service_name = "${var.project}-${var.env}-email-worker-service"
  ecs_cluster_name          = "${var.project}-${var.env}-cluster"
}
##################################################
# IAM Role (for ECS task)
##################################################
resource "aws_appautoscaling_target" "email_worker_desired_count" {
  max_capacity       = 5
  min_capacity       = 1
  resource_id        = "service/${local.ecs_cluster_name}/${local.email_worker_service_name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}
resource "aws_appautoscaling_policy" "email_worker_scale_out" {
  name               = "${var.project}-${var.env}-email-worker-scale-out"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.email_worker_desired_count.resource_id
  scalable_dimension = aws_appautoscaling_target.email_worker_desired_count.scalable_dimension
  service_namespace  = aws_appautoscaling_target.email_worker_desired_count.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 30
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 1
    }
  }
}
resource "aws_appautoscaling_policy" "email_worker_scale_in" {
  name               = "${var.project}-${var.env}-email-worker-scale-in"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.email_worker_desired_count.resource_id
  scalable_dimension = aws_appautoscaling_target.email_worker_desired_count.scalable_dimension
  service_namespace  = aws_appautoscaling_target.email_worker_desired_count.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = -1
    }
  }
}
resource "aws_cloudwatch_metric_alarm" "email_worker_queue_high" {
  alarm_name          = "${var.project}-${var.env}-email-worker-queue-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 30
  statistic           = "Average"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = local.notifications_queue_name
  }

  alarm_actions = [aws_appautoscaling_policy.email_worker_scale_out.arn]
}
resource "aws_cloudwatch_metric_alarm" "email_worker_queue_low" {
  alarm_name          = "${var.project}-${var.env}-email-worker-queue-low"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Average"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = local.notifications_queue_name
  }

  alarm_actions = [aws_appautoscaling_policy.email_worker_scale_in.arn]
}
resource "aws_iam_role" "task_role" {
  name = "${var.project}-${var.env}-notification-api-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = var.project
    Environment = var.env
    Service     = "notification-api"
  }
}
