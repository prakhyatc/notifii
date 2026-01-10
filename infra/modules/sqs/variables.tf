variable "name" {
  description = "Base name for the queue (without env suffixes)."
  type        = string
}

variable "env" {
  description = "Environment name, e.g. dev."
  type        = string
}

variable "max_receive_count" {
  description = "How many times a message can be received before moving to the DLQ."
  type        = number
  default     = 5
}

variable "message_retention_seconds" {
  description = "Retention period for messages in seconds."
  type        = number
  default     = 345600 # 4 days
}

variable "visibility_timeout_seconds" {
  description = "Visibility timeout for message processing."
  type        = number
  default     = 30
}
