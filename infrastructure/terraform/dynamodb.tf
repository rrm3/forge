resource "aws_dynamodb_table" "sessions" {
  name         = "${local.prefix}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "session_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "session_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}

resource "aws_dynamodb_table" "profiles" {
  name         = "${local.prefix}-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}

resource "aws_dynamodb_table" "journal" {
  name         = "${local.prefix}-journal"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "entry_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "entry_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}

resource "aws_dynamodb_table" "ideas" {
  name         = "${local.prefix}-ideas"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "idea_id"

  attribute {
    name = "idea_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Project     = "forge"
  }
}
