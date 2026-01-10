output "task_execution_role_arn" {
  description = "IAM role ARN used by ECS agent to pull images + write logs"
  value       = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  description = "IAM role ARN assumed by the application container for AWS API calls"
  value       = aws_iam_role.task.arn
}
output "task_role_name" {
  value = aws_iam_role.task.name
}