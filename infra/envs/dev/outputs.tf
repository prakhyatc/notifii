output "notification_api_alb_dns" {
  value = module.ecs_notification_api.alb_dns_name
}
output "notification_api_repo_url" {
  value = module.ecr_notification_api.repo_url
}
output "notifications_queue_url" {
  value = module.sqs_notifications.queue_url
}

output "notifications_queue_arn" {
  value = module.sqs_notifications.queue_arn
}