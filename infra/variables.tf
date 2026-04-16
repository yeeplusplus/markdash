variable "aws_region" {
  description = "AWS region for the markdash stack"
  type        = string
  default     = "us-east-1"
}

variable "operator_ip_cidr" {
  description = "CIDR allowed to SSH to the instance (e.g. 203.0.113.4/32)"
  type        = string
}

variable "repo_url" {
  description = "Git HTTPS URL of the markdash repo cloned onto the instance"
  type        = string
}

variable "git_ref" {
  description = "Branch, tag, or commit SHA to check out"
  type        = string
  default     = "main"
}

variable "anthropic_api_key" {
  description = "Anthropic API key rendered into /opt/app/.env"
  type        = string
  sensitive   = true
}

variable "polymarket_base_url" {
  description = "Base URL for the Polymarket Gamma API"
  type        = string
  default     = "https://gamma-api.polymarket.com"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key uploaded to the key pair"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small"
}

variable "project_tag" {
  description = "Value for the Project tag applied to all resources"
  type        = string
  default     = "markdash"
}

variable "domain_name" {
  description = "Public FQDN for the app (e.g. markdash.example.com). Must live in route53_zone_id."
  type        = string
}

variable "route53_zone_id" {
  description = "Existing Route53 hosted zone id that owns domain_name"
  type        = string
}

variable "origin_subdomain" {
  description = "Subdomain prefix used as the CloudFront origin hostname (origin.<domain_name>)"
  type        = string
  default     = "origin"
}
