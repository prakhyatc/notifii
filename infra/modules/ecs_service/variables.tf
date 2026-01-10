variable "project" { type = string }
variable "env" { type = string }

variable "vpc_id" { type = string }

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "service_name" { type = string }

variable "container_image" {
  type        = string
  description = "ECR image URL (including tag), e.g. <repo_url>:dev"
}

variable "container_port" {
  type    = number
  default = 8000
}

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
  description = "SQS queue URL for notification service"
  type        = string
}


variable "task_execution_role_arn" { type = string }
variable "task_role_arn" { type = string }