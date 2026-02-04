resource "aws_security_group" "jenkins_sg" {
  name        = "jenkins-sg"
  description = "Allow SSH and convenient ports for Jenkins"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"] # Internal VPC access only
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Get latest Amazon Linux 2 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "jenkins_agent" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.medium"
  subnet_id     = module.vpc.private_subnets[0]

  iam_instance_profile = aws_iam_instance_profile.jenkins_profile.name
  vpc_security_group_ids = [aws_security_group.jenkins_sg.id]

  tags = {
    Name = "Jenkins-Agent-Node"
    Role = "CI-CD"
  }

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              yum install -y git docker
              yum install -y java-17-amazon-corretto
              
              # Install Jenkins
              wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo
              rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io.key
              yum install jenkins -y
              
              # Start Services
              systemctl enable docker
              systemctl start docker
              systemctl enable jenkins
              systemctl start jenkins
              
              # Permissions
              usermod -aG docker jenkins
              EOF
}
