resource "aws_cognito_user_pool_client" "forge" {
  name         = "${local.prefix}-spa"
  user_pool_id = var.cognito_user_pool_id

  # No client secret for SPA
  generate_secret = false

  # Token validity
  access_token_validity  = 1  # 1 hour
  id_token_validity      = 1  # 1 hour
  refresh_token_validity = 30 # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # OAuth flows - implicit for SPA
  allowed_oauth_flows                  = ["implicit"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["email", "openid", "profile"]

  callback_urls = concat(
    ["https://${var.cloudfront_domain}/callback"],
    ["http://localhost:5173/callback"]
  )

  logout_urls = concat(
    ["https://${var.cloudfront_domain}/logout"],
    ["http://localhost:5173/logout"]
  )

  supported_identity_providers = ["COGNITO"]

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_CUSTOM_AUTH",
  ]

  prevent_user_existence_errors = "ENABLED"

  read_attributes = [
    "email",
    "email_verified",
    "name",
  ]

  write_attributes = [
    "email",
    "name",
  ]
}
