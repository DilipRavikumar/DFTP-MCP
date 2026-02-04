terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
  required_version = ">= 1.2.0"
}

provider "aws" {
  region = var.region

  # dynamic "assume_role" block to optionally assume a role
  dynamic "assume_role" {
    for_each = var.iam_role_arn != "" ? [1] : []
    content {
      role_arn = var.iam_role_arn
    }
  }
}
