module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "dftp-mcp-keycloak-db"

  engine            = "postgres"
  engine_version    = "14"
  family            = "postgres14" # Required for parameter group
  major_engine_version = "14"      # Required for option group
  instance_class    = "db.t3.micro"
  allocated_storage = 20

  db_name  = "keycloak"
  username = "keycloak"
  port     = "5432"

  iam_database_authentication_enabled = true

  vpc_security_group_ids = [module.vpc.default_security_group_id]

  # DB subnet group
  create_db_subnet_group = true
  subnet_ids             = module.vpc.private_subnets

  # Database Deletion Protection
  deletion_protection = false # Set to true for production

  tags = {
    Owner       = "user"
    Environment = "dev"
  }
}
