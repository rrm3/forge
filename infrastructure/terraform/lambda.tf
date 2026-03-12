# ECR repository for the backend Docker image
resource "aws_ecr_repository" "backend" {
  name                 = "${local.prefix}-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}

# CloudWatch log group
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/aws/lambda/${local.prefix}-backend"
  retention_in_days = 14

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}

# IAM role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${local.prefix}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "${local.prefix}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:*:table/forge-*",
        ]
      },
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetObjectVersion",
          "s3:DeleteObjectVersion",
        ]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*",
        ]
      },
      {
        Sid    = "BedrockAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = [
          # Claude models
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-*",
          # Cohere embed
          "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.embed-*",
          # Cohere rerank
          "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.rerank-*",
        ]
      },
    ]
  })
}

# Lambda function
resource "aws_lambda_function" "backend" {
  function_name = "${local.prefix}-backend"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.backend.repository_url}:latest"
  memory_size   = 1024
  timeout       = 900

  environment {
    variables = {
      COGNITO_USER_POOL_ID  = var.cognito_user_pool_id
      COGNITO_CLIENT_ID     = aws_cognito_user_pool_client.forge.id
      COGNITO_REGION        = var.aws_region
      DYNAMODB_TABLE_PREFIX = local.prefix
      AWS_REGION_NAME       = var.aws_region
      S3_BUCKET             = aws_s3_bucket.data.bucket
      LANCE_BACKEND         = "s3"
      LANCE_S3_BUCKET       = aws_s3_bucket.data.bucket
      LLM_MODEL             = "anthropic.claude-sonnet-4-20250514-v1:0"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.backend,
    aws_iam_role_policy_attachment.lambda_basic,
  ]

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}

# Lambda Function URL with streaming
resource "aws_lambda_function_url" "backend" {
  function_name      = aws_lambda_function.backend.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"
}

# Permission for function URL invocation
resource "aws_lambda_permission" "function_url" {
  statement_id           = "AllowFunctionURLInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.backend.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
