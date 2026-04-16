locals {
  origin_fqdn = "${var.origin_subdomain}.${var.domain_name}"
}

# -- Origin record: <origin_subdomain>.<domain_name> -> Elastic IP --
# CloudFront needs a DNS name as origin; we give it a dedicated subdomain that
# points directly at the EC2 EIP. This hostname is also useful for debugging.
resource "aws_route53_record" "origin" {
  zone_id = var.route53_zone_id
  name    = local.origin_fqdn
  type    = "A"
  ttl     = 60
  records = [aws_eip.app.public_ip]
}

# -- ACM cert in us-east-1 (required by CloudFront) --
resource "aws_acm_certificate" "main" {
  provider          = aws.us_east_1
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id         = var.route53_zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 60
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "main" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# -- CloudFront distribution (HTTPS termination) --
resource "aws_cloudfront_distribution" "app" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${var.project_tag} - ${var.domain_name}"
  aliases         = [var.domain_name]
  price_class     = "PriceClass_100"

  origin {
    domain_name = local.origin_fqdn
    origin_id   = "ec2-origin"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "http-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  default_cache_behavior {
    target_origin_id         = "ec2-origin"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    # Managed-CachingDisabled: always go to origin. The API returns live data;
    # static assets can be revisited with a separate cache behavior later.
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    # Managed-AllViewerExceptHostHeader: forward everything but Host so the
    # origin sees its own origin_fqdn rather than the CloudFront-facing domain.
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.main.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# -- Public A-ALIAS: <domain_name> -> CloudFront --
resource "aws_route53_record" "app" {
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.app.domain_name
    zone_id                = aws_cloudfront_distribution.app.hosted_zone_id
    evaluate_target_health = false
  }
}
