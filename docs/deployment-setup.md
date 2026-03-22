# AI Tuesdays (Forge) - Deployment Setup

## What's Built

The app is fully implemented and pushed to https://github.com/rrm3/forge.git

* **Backend:** Python FastAPI with ReAct agentic loop, LanceDB RAG, Cohere embeddings, 9 tools, 4 skills
* **Frontend:** React + Vite + Tailwind SPA with OIDC auth (Digital Science ID), SSE streaming chat, session management
* **Infrastructure:** CDK stack for Lambda + Function URL, DynamoDB, S3, CloudFront
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

This is NOT part of ds-identity. It's a generic AWS account setting that allows any GitHub repo (that you authorize) to authenticate with AWS. ds-identity is about user authentication (OIDC). This is about CI/CD authentication.

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
* AmazonDynamoDBFullAccess (CDK)

Or scope it down to specific resources after initial setup.

### 3. Deploy Infrastructure with CDK

```bash
cd infrastructure/cdk
npm install
npx cdk bootstrap aws://ACCOUNT_ID/us-east-1  # one-time
npx cdk deploy --context environment=production
```

This creates: ECR repo, Lambda function, DynamoDB tables, S3 buckets, CloudFront distribution.

Note the outputs - you'll need them for step 4.

### 4. Set GitHub Secrets

After CDK deploy, set these secrets on the repo using the stack outputs:

```bash
cd /Users/rmcgrath/dev/forge

# From step 2
gh secret set AWS_DEPLOY_ROLE_ARN --body "arn:aws:iam::ACCOUNT_ID:role/forge-github-actions"

# From CDK outputs
gh secret set ECR_REPOSITORY --body "forge-production-backend"
gh secret set LAMBDA_FUNCTION_NAME --body "forge-production-backend"
gh secret set FRONTEND_BUCKET --body "forge-production-frontend"
gh secret set CLOUDFRONT_DISTRIBUTION_ID --body "<from CDK output>"

# OIDC (Digital Science ID)
gh secret set OIDC_PROVIDER_URL --body "https://id.digitalscience.ai"
gh secret set OIDC_CLIENT_ID --body "<from ds-identity client registration>"
```

### 5. Push Initial Docker Image

The Lambda function needs an initial image before the GH Actions workflow can update it. After ECR is created:

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/forge-production-backend:initial .
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/forge-production-backend:initial

# Update Lambda to use it
aws lambda update-function-code \
  --function-name forge-production-backend \
  --image-uri ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/forge-production-backend:initial
```

### 6. Set Lambda Environment Variables

The Lambda function needs these env vars (CDK sets most of them, but verify):

* OIDC_PROVIDER_URL
* OIDC_CLIENT_ID
* DYNAMODB_TABLE_PREFIX=forge-production
* S3_BUCKET=forge-production-data
* LANCE_BACKEND=s3
* LANCE_S3_BUCKET=forge-production-data
* LLM_MODEL=anthropic/claude-sonnet-4-20250514
* DEV_MODE=false
* AWS_LWA_INVOKE_MODE=response_stream

### 7. Index Curriculum

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

Infrastructure changes: run `npx cdk deploy` locally or add a CDK deploy job to the workflow.

## Local Development

```bash
cd /Users/rmcgrath/dev/forge
source .envrc              # sets DEV_MODE=true
./scripts/start-local.sh   # starts backend :8000 + frontend :5173
```

Open http://localhost:5173. In dev mode, auth is bypassed (uses X-Dev-User-Id header, defaults to "alice"). LLM calls require `ANTHROPIC_API_KEY` env var or AWS Bedrock credentials.

## Open Items

* **Delete accidental repo:** https://github.com/digital-science/forge needs to be deleted (requires org admin or `delete_repo` scope)
* **Custom domain:** If you want forge.digital-science.com, you'll need an ACM certificate and Route53/DNS entry. Set `domainName` and `acmCertificateArn` CDK context values.
* **Curriculum content:** The test-curriculum is placeholder. Real AI Tuesdays curriculum needs to be authored and uploaded to S3.
* **User profile pre-population:** Need a script or process to import DS org data into the profiles DynamoDB table.
* **Memory extraction:** The periodic Lambda that extracts memory from session transcripts is designed but not implemented yet. Could be a scheduled Lambda or a cron script.
