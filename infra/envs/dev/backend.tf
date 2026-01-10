terraform {
  backend "s3" {
    bucket         = "notifii-tfstate-dev-123456"
    key            = "infra/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "notifii-terraform-locks"
    encrypt        = true
  }
}
