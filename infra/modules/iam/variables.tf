variable "project" {
  type = string
}

variable "env" {
  type = string
}

# Optional: if you want to attach extra policies later without rewriting the module
variable "task_role_policy_json" {
  type        = string
  description = "Optional inline IAM policy JSON to attach to the task role (for app permissions)."
  default     = null
}