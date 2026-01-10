locals {
  name = "${var.project}-${var.env}"

  common_tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
  }
}

# ECS tasks assume these roles
data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

############################################
# 1) Task EXECUTION role (ECS agent needs it)
############################################
resource "aws_iam_role" "task_execution" {
  name               = "${local.name}-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = local.common_tags
}

# Attach AWS managed policy that includes:
# - ECR image pull
# - CloudWatch Logs writes
resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Optional but common: allow pulling images encrypted with KMS (if you enable that later)
# You can add later if needed.

############################################
# 2) Task role (YOUR APP uses this)
############################################
resource "aws_iam_role" "task" {
  name               = "${local.name}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = local.common_tags
}

# Optional: attach an inline policy for app permissions (SQS/DDB/X-Ray) later
resource "aws_iam_role_policy" "task_inline" {
  count = var.task_role_policy_json == null ? 0 : 1

  name   = "${local.name}-task-inline-policy"
  role   = aws_iam_role.task.id
  policy = var.task_role_policy_json
}