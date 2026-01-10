variable "project" { type = string }
variable "env" { type = string }

variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }

variable "service_name" { type = string }
variable "container_image" { type = string }

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "notifii_queue_url" {
  description = "SQS queue URL for worker to consume."
  type        = string
}

variable "task_execution_role_arn" { type = string }
variable "task_role_arn" { type = string }
