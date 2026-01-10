resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-${var.env}-dlq"
  message_retention_seconds = var.message_retention_seconds
}

resource "aws_sqs_queue" "queue" {
  name                       = "${var.name}-${var.env}-queue"
  message_retention_seconds  = var.message_retention_seconds
  visibility_timeout_seconds = var.visibility_timeout_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}
