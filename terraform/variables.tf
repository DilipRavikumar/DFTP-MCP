variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "dftp-mcp-cluster"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "iam_role_arn" {
  description = "ARN of the IAM role to assume for deployment"
  type        = string
  default     = "" # Optional: Leave empty to use default credentials
}
