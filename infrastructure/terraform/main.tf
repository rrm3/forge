terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment and configure before first use
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "forge/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "your-terraform-locks-table"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region
}

locals {
  prefix = "forge-${var.environment}"
}
