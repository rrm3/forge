variable "environment" {
  description = "Environment name (e.g., dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "cognito_user_pool_id" {
  description = "ID of the existing central-login Cognito user pool"
  type        = string
}

variable "cloudfront_domain" {
  description = "CloudFront distribution domain (used in Cognito callback URLs)"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository in format owner/repo (for OIDC trust policy)"
  type        = string
  default     = "rrm3/forge"
}

variable "domain_name" {
  description = "Custom domain name for the CloudFront distribution (leave empty to skip)"
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for custom domain (must be in us-east-1)"
  type        = string
  default     = ""
}
