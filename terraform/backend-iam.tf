# IAM Role for Backend to access AWS Bedrock via IRSA (IAM Roles for Service Accounts)

data "aws_iam_policy_document" "backend_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.oidc_provider_arn, "/^(.*provider/)/", "")}:sub"
      values   = ["system:serviceaccount:dftp-mcp:backend-sa"]
    }
  }
}

resource "aws_iam_role" "backend_bedrock" {
  name               = "dftp-backend-bedrock-role"
  assume_role_policy = data.aws_iam_policy_document.backend_assume_role.json

  tags = {
    Environment = "dev"
    Terraform   = "true"
  }
}

resource "aws_iam_role_policy" "backend_bedrock_access" {
  name = "bedrock-access"
  role = aws_iam_role.backend_bedrock.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      }
    ]
  })
}

output "backend_role_arn" {
  value       = aws_iam_role.backend_bedrock.arn
  description = "IAM Role ARN for backend service account"
}
