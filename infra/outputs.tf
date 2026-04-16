output "public_ip" {
  description = "Elastic IP bound to the instance (also the CloudFront origin)"
  value       = aws_eip.app.public_ip
}

output "instance_id" {
  description = "EC2 instance id"
  value       = aws_instance.app.id
}

output "ssh_command" {
  description = "SSH command for the operator"
  value       = "ssh ec2-user@${aws_eip.app.public_ip}"
}

output "origin_url" {
  description = "Direct origin URL (HTTP) - useful for debugging without CloudFront"
  value       = "http://${aws_route53_record.origin.fqdn}/"
}

output "live_url" {
  description = "Public HTTPS URL of the markdash app (via CloudFront)"
  value       = "https://${var.domain_name}/"
}

output "healthz_url" {
  description = "Health probe URL (via CloudFront)"
  value       = "https://${var.domain_name}/healthz"
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain (for debugging)"
  value       = aws_cloudfront_distribution.app.domain_name
}
