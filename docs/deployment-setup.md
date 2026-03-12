# AI Tuesdays (Forge) - Deployment Setup

## What's Built

The app is fully implemented and pushed to https://github.com/rrm3/forge.git

* **Backend:** Python FastAPI with ReAct agentic loop, LanceDB RAG, Cohere embeddings, 9 tools, 4 skills
* **Frontend:** React + Vite + Tailwind SPA with Cognito auth, SSE streaming chat, session management
* **Infrastructure:** Terraform configs for Lambda + Function URL, DynamoDB, S3, CloudFront
* **CI/CD:** GitHub Actions workflow at `.github/workflows/deploy.yml` (deploys on push to main)
* **Tests:** 197 passing tests

## What Needs To Happen Before First Deploy

### 1. AWS OIDC Provider (one-time, account-level)

GitHub Actions needs to assume an IAM role in your AWS account without static keys. This uses OpenID Connect federation. The OIDC provider may already exist in the DS AWS account (check IAM > Identity providers for `token.actions.githubusercontent.com`). If not:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

This is NOT part of ds-identity. It's a generic AWS account setting that allows any GitHub repo (that you authorize) to authenticate with AWS. ds-identity is about user authentication (Cognito). This is about CI/CD authentication.

### 2. Create IAM Deploy Role

Create a role that GitHub Actions will assume. Trust policy restricts it to the rrm3/forge repo:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:rrm3/forge:*"
        }
      }
    }
  ]
}
```

Attach these managed policies (or create a custom one):
* AmazonEC2ContainerRegistryPowerUser (ECR push)
* AWSLambda_FullAccess (update function code)
* AmazonS3FullAccess (frontend deploy)
* CloudFrontFullAccess (cache invalidation)
* AmazonDynamoDBFullAccess (Terraform)

Or scope it down to specific resources after initial setup.

### 3. Configure Terraform Backend

Edit `infrastructure/terraform/main.tf` - uncomment and configure the S3 backend for state storage:

```hcl
backend "s3" {
  bucket = "your-terraform-state-bucket"
  key    = "forge/terraform.tfstate"
  region = "us-east-1"
}
```

Or use local state initially (already the default).

### 4. Run Terraform (first time, from local machine)

```bash
cd infrastructure/terraform
export TF_VAR_cognito_user_pool_id="us-east-1_Gtq9PeFdk"  # from ds-identity
terraform init
terraform plan
terraform apply
```

This creates: ECR repo, Lambda function, DynamoDB tables, S3 buckets, CloudFront distribution, Cognito app client.

Note the outputs - you'll need them for step 5.

### 5. Set GitHub Secrets

After Terraform apply, set these secrets on the repo:

```bash
cd /Users/rmcgrath/dev/forge

# From step 2
gh secret set AWS_DEPLOY_ROLE_ARN --body "arn:aws:iam::ACCOUNT_ID:role/forge-deploy"

# From Terraform outputs
gh secret set ECR_REPOSITORY --body "$(cd infrastructure/terraform && terraform output -raw ecr_repository_url | cut -d/ -f2)"
gh secret set LAMBDA_FUNCTION_NAME --body "forge-production"
gh secret set FRONTEND_BUCKET --body "$(cd infrastructure/terraform && terraform output -raw frontend_bucket_name)"
gh secret set CLOUDFRONT_DISTRIBUTION_ID --body "$(cd infrastructure/terraform && terraform output -raw cloudfront_distribution_id 2>/dev/null || echo 'TODO')"

# From ds-identity Cognito config
gh secret set COGNITO_USER_POOL_ID --body "us-east-1_Gtq9PeFdk"
gh secret set COGNITO_CLIENT_ID --body "$(cd infrastructure/terraform && terraform output -raw cognito_client_id)"
```

### 6. Push Initial Docker Image

The Lambda function needs an initial image before the GH Actions workflow can update it. After ECR is created:

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/forge-production:initial .
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/forge-production:initial

# Update Lambda to use it
aws lambda update-function-code \
  --function-name forge-production \
  --image-uri ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/forge-production:initial
```

### 7. Set Lambda Environment Variables

The Lambda function needs these env vars (Terraform should set most of them, but verify):

* COGNITO_USER_POOL_ID
* COGNITO_CLIENT_ID
* COGNITO_REGION=us-east-1
* DYNAMODB_TABLE_PREFIX=forge-production
* S3_BUCKET=forge-production-data
* LANCE_BACKEND=s3
* LANCE_S3_BUCKET=forge-production-data
* LLM_MODEL=anthropic/claude-sonnet-4-20250514
* DEV_MODE=false
* AWS_LWA_INVOKE_MODE=response_stream

### 8. Index Curriculum

Once infrastructure is up, populate the LanceDB curriculum index:

```bash
python scripts/index_curriculum.py --bucket forge-production-data --prefix curriculum/
```

First upload curriculum files to S3:
```bash
aws s3 sync ./test-curriculum/ s3://forge-production-data/curriculum/
```

## After Setup - Normal Workflow

Every push to main triggers the GH Actions workflow:
1. Tests run
2. Backend Docker image built and pushed to ECR, Lambda updated
3. Frontend built and synced to S3, CloudFront invalidated

Infrastructure changes: trigger manually via workflow_dispatch with `deploy_infra: true`, or run `terraform apply` locally.

## Local Development

```bash
cd /Users/rmcgrath/dev/forge
source .envrc              # sets DEV_MODE=true
./scripts/start-local.sh   # starts backend :8000 + frontend :5173
```

Open http://localhost:5173. In dev mode, auth is bypassed (uses X-Dev-User-Id header, defaults to "alice"). LLM calls require `ANTHROPIC_API_KEY` env var or AWS Bedrock credentials.

## Open Items

* **Delete accidental repo:** https://github.com/digital-science/forge needs to be deleted (requires org admin or `delete_repo` scope)
* **Cognito app client:** Verify the Terraform-created client works with the central-login pool. May need coordination with whoever manages ds-identity.
* **Custom domain:** If you want forge.digital-science.com, you'll need an ACM certificate and Route53/DNS entry. Set `domain_name` and `acm_certificate_arn` Terraform variables.
* **Curriculum content:** The test-curriculum is placeholder. Real AI Tuesdays curriculum needs to be authored and uploaded to S3.
* **User profile pre-population:** Need a script or process to import DS org data into the profiles DynamoDB table.
* **Memory extraction:** The periodic Lambda that extracts memory from session transcripts is designed but not implemented yet. Could be a scheduled Lambda or a cron script.
