terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project = var.project_tag
      Stack   = "markdash"
    }
  }
}

# CloudFront requires ACM certs in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project = var.project_tag
      Stack   = "markdash"
    }
  }
}

# Latest Amazon Linux 2023 x86_64 AMI
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "operator" {
  key_name   = "${var.project_tag}-operator"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_security_group" "app" {
  name        = "${var.project_tag}-app"
  description = "markdash: SSH from operator, HTTP from world"

  ingress {
    description = "SSH from operator"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.operator_ip_cidr]
  }

  ingress {
    description = "HTTP from world"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "all egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.operator.key_name
  vpc_security_group_ids = [aws_security_group.app.id]

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    repo_url            = var.repo_url
    git_ref             = var.git_ref
    anthropic_api_key   = var.anthropic_api_key
    polymarket_base_url = var.polymarket_base_url
  })

  # re-run user_data if the template or its inputs change
  user_data_replace_on_change = true

  tags = {
    Name = "${var.project_tag}-app"
  }
}

resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name = "${var.project_tag}-eip"
  }
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}
