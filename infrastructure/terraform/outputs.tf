output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name (for Cognito callback URLs)"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "function_url" {
  description = "Lambda function URL"
  value       = aws_lambda_function_url.backend.function_url
}

output "data_bucket_name" {
  description = "S3 data bucket name"
  value       = aws_s3_bucket.data.bucket
}

output "frontend_bucket_name" {
  description = "S3 frontend bucket name"
  value       = aws_s3_bucket.frontend.bucket
}

output "ecr_repository_url" {
  description = "ECR repository URL for the backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "cognito_client_id" {
  description = "Cognito app client ID for the SPA"
  value       = aws_cognito_user_pool_client.forge.id
}
