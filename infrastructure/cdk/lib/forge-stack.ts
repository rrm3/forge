import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

interface ForgeStackProps extends cdk.StackProps {
  environment: string;
}

export class ForgeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ForgeStackProps) {
    super(scope, id, props);

    const { environment } = props;
    const prefix = `forge-${environment}`;

    // Context parameters (equivalent to Terraform variables)
    const cognitoUserPoolId = this.node.tryGetContext('cognitoUserPoolId') || '';
    const cloudfrontDomain = this.node.tryGetContext('cloudfrontDomain') || '';
    const githubRepo = this.node.tryGetContext('githubRepo') || 'rrm3/forge';
    const domainName = this.node.tryGetContext('domainName') || '';
    const acmCertificateArn = this.node.tryGetContext('acmCertificateArn') || '';

    const tags: Record<string, string> = {
      Environment: environment,
      Project: 'forge',
    };

    // Apply tags to all resources in this stack
    Object.entries(tags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    // ---------------------------------------------------------------
    // ECR Repository
    // ---------------------------------------------------------------
    const ecrRepository = new ecr.Repository(this, 'BackendRepository', {
      repositoryName: `${prefix}-backend`,
      imageScanOnPush: true,
      imageTagMutability: ecr.TagMutability.MUTABLE,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ---------------------------------------------------------------
    // DynamoDB Tables
    // ---------------------------------------------------------------
    const sessionsTable = new dynamodb.Table(this, 'SessionsTable', {
      tableName: `${prefix}-sessions`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'session_id', type: dynamodb.AttributeType.STRING },
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const profilesTable = new dynamodb.Table(this, 'ProfilesTable', {
      tableName: `${prefix}-profiles`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const journalTable = new dynamodb.Table(this, 'JournalTable', {
      tableName: `${prefix}-journal`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'entry_id', type: dynamodb.AttributeType.STRING },
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const ideasTable = new dynamodb.Table(this, 'IdeasTable', {
      tableName: `${prefix}-ideas`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'idea_id', type: dynamodb.AttributeType.STRING },
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ---------------------------------------------------------------
    // S3 Buckets
    // ---------------------------------------------------------------

    // Data bucket - transcripts, memory, curriculum, lance
    const dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: `${prefix}-data`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Frontend bucket - SPA hosting (served via CloudFront OAC)
    const frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: `${prefix}-frontend`,
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html',
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ---------------------------------------------------------------
    // Cognito User Pool Client (against an external pool)
    // ---------------------------------------------------------------
    const userPool = cognito.UserPool.fromUserPoolId(this, 'ExternalUserPool', cognitoUserPoolId);

    const callbackUrls = [
      `https://${cloudfrontDomain || 'placeholder.cloudfront.net'}/callback`,
      'http://localhost:5173/callback',
    ];
    const logoutUrls = [
      `https://${cloudfrontDomain || 'placeholder.cloudfront.net'}/logout`,
      'http://localhost:5173/logout',
    ];

    const userPoolClient = new cognito.UserPoolClient(this, 'UserPoolClient', {
      userPool,
      userPoolClientName: `${prefix}-spa`,
      generateSecret: false,
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      oAuth: {
        flows: {
          implicitCodeGrant: true,
        },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls,
        logoutUrls,
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
      ],
      authFlows: {
        userSrp: true,
        custom: true,
      },
      preventUserExistenceErrors: true,
      readAttributes: new cognito.ClientAttributes()
        .withStandardAttributes({
          email: true,
          emailVerified: true,
          fullname: true,
        }),
      writeAttributes: new cognito.ClientAttributes()
        .withStandardAttributes({
          email: true,
          fullname: true,
        }),
    });

    // ---------------------------------------------------------------
    // CloudWatch Log Group
    // ---------------------------------------------------------------
    const logGroup = new logs.LogGroup(this, 'BackendLogGroup', {
      logGroupName: `/aws/lambda/${prefix}-backend`,
      retention: logs.RetentionDays.TWO_WEEKS,
    });

    // ---------------------------------------------------------------
    // Lambda IAM Role
    // ---------------------------------------------------------------
    const lambdaRole = new iam.Role(this, 'LambdaRole', {
      roleName: `${prefix}-lambda`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
    });

    // Basic execution (CloudWatch logs)
    lambdaRole.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
    );

    // DynamoDB access
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'DynamoDBAccess',
      actions: [
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:DeleteItem',
        'dynamodb:Query',
        'dynamodb:Scan',
        'dynamodb:BatchGetItem',
        'dynamodb:BatchWriteItem',
      ],
      resources: [
        `arn:aws:dynamodb:${this.region}:${this.account}:table/forge-*`,
      ],
    }));

    // S3 access
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'S3Access',
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject',
        's3:ListBucket',
        's3:GetObjectVersion',
        's3:DeleteObjectVersion',
      ],
      resources: [
        dataBucket.bucketArn,
        `${dataBucket.bucketArn}/*`,
      ],
    }));

    // Bedrock access
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'BedrockAccess',
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-*`,
        `arn:aws:bedrock:${this.region}::foundation-model/cohere.embed-*`,
        `arn:aws:bedrock:${this.region}::foundation-model/cohere.rerank-*`,
      ],
    }));

    // ---------------------------------------------------------------
    // Lambda Function (container image from ECR)
    // ---------------------------------------------------------------
    const backendFunction = new lambda.DockerImageFunction(this, 'BackendFunction', {
      functionName: `${prefix}-backend`,
      code: lambda.DockerImageCode.fromEcr(ecrRepository, { tagOrDigest: 'latest' }),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(900),
      role: lambdaRole,
      environment: {
        COGNITO_USER_POOL_ID: cognitoUserPoolId,
        COGNITO_CLIENT_ID: userPoolClient.userPoolClientId,
        COGNITO_REGION: this.region,
        DYNAMODB_TABLE_PREFIX: prefix,
        AWS_REGION_NAME: this.region,
        S3_BUCKET: dataBucket.bucketName,
        LANCE_BACKEND: 's3',
        LANCE_S3_BUCKET: dataBucket.bucketName,
        LLM_MODEL: 'anthropic.claude-sonnet-4-20250514-v1:0',
      },
      logGroup,
    });

    // Lambda Function URL with streaming
    const functionUrl = backendFunction.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      invokeMode: lambda.InvokeMode.RESPONSE_STREAM,
    });

    // ---------------------------------------------------------------
    // CloudFront Distribution
    // ---------------------------------------------------------------

    // S3 Origin Access Control for the frontend bucket
    const oac = new cloudfront.S3OriginAccessControl(this, 'FrontendOAC', {
      originAccessControlName: `${prefix}-frontend-oac`,
      description: 'OAC for Forge frontend bucket',
    });

    // S3 origin using OAC
    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(frontendBucket, {
      originAccessControl: oac,
    });

    // Lambda function URL origin
    // Strip the https:// and trailing slash from the function URL for the domain name
    const lambdaOrigin = new origins.FunctionUrlOrigin(functionUrl, {});

    // Build optional custom domain configuration
    const certificate = acmCertificateArn
      ? acm.Certificate.fromCertificateArn(this, 'Certificate', acmCertificateArn)
      : undefined;

    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      enabled: true,
      defaultRootObject: 'index.html',
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      comment: `${prefix} distribution`,
      domainNames: domainName ? [domainName] : undefined,
      certificate,
      minimumProtocolVersion: certificate ? cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021 : undefined,
      sslSupportMethod: certificate ? cloudfront.SSLMethod.SNI : undefined,

      defaultBehavior: {
        origin: s3Origin,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        compress: true,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },

      additionalBehaviors: {
        '/api/*': {
          origin: lambdaOrigin,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          compress: true,
          cachePolicy: new cloudfront.CachePolicy(this, 'ApiCachePolicy', {
            cachePolicyName: `${prefix}-api-no-cache`,
            minTtl: cdk.Duration.seconds(0),
            defaultTtl: cdk.Duration.seconds(0),
            maxTtl: cdk.Duration.seconds(0),
            headerBehavior: cloudfront.CacheHeaderBehavior.allowList('Authorization', 'Content-Type', 'Accept'),
            queryStringBehavior: cloudfront.CacheQueryStringBehavior.all(),
            cookieBehavior: cloudfront.CacheCookieBehavior.all(),
          }),
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        },
      },

      // SPA routing: return index.html for 403/404 from S3
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
      ],
    });

    // ---------------------------------------------------------------
    // GitHub Actions OIDC Provider and Role
    // ---------------------------------------------------------------
    const githubOidcProvider = new iam.OpenIdConnectProvider(this, 'GitHubActionsOIDC', {
      url: 'https://token.actions.githubusercontent.com',
      clientIds: ['sts.amazonaws.com'],
      thumbprints: [
        '6938fd4d98bab03faadb97b34396831e3780aea1',
        '1c58a3a8518e8759bf075b76b750d4f2df264fcd',
      ],
    });

    const githubActionsRole = new iam.Role(this, 'GitHubActionsRole', {
      roleName: 'forge-github-actions',
      assumedBy: new iam.FederatedPrincipal(
        githubOidcProvider.openIdConnectProviderArn,
        {
          StringEquals: {
            'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
          },
          StringLike: {
            'token.actions.githubusercontent.com:sub': `repo:${githubRepo}:*`,
          },
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
    });

    // Terraform state access (kept for compatibility, also applies to CDK state if using S3 backend)
    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'TerraformState',
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject',
        's3:ListBucket',
      ],
      resources: [
        'arn:aws:s3:::forge-terraform-state',
        'arn:aws:s3:::forge-terraform-state/*',
      ],
    }));

    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'TerraformLocks',
      actions: [
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:DeleteItem',
        'dynamodb:DescribeTable',
      ],
      resources: [
        `arn:aws:dynamodb:${this.region}:${this.account}:table/forge-terraform-locks`,
      ],
    }));

    // Terraform/CDK resource management
    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'TerraformResourceManagement',
      actions: [
        // Cognito
        'cognito-idp:CreateUserPoolClient',
        'cognito-idp:UpdateUserPoolClient',
        'cognito-idp:DescribeUserPoolClient',
        'cognito-idp:DeleteUserPoolClient',
        'cognito-idp:DescribeUserPool',
        // DynamoDB
        'dynamodb:CreateTable',
        'dynamodb:UpdateTable',
        'dynamodb:DescribeTable',
        'dynamodb:DescribeContinuousBackups',
        'dynamodb:UpdateContinuousBackups',
        'dynamodb:ListTagsOfResource',
        'dynamodb:TagResource',
        'dynamodb:UntagResource',
        // S3
        's3:CreateBucket',
        's3:PutBucketVersioning',
        's3:GetBucketVersioning',
        's3:PutBucketEncryption',
        's3:GetBucketEncryption',
        's3:PutPublicAccessBlock',
        's3:GetPublicAccessBlock',
        's3:PutBucketPolicy',
        's3:GetBucketPolicy',
        's3:DeleteBucketPolicy',
        's3:GetBucketAcl',
        's3:GetBucketCORS',
        's3:GetBucketWebsite',
        's3:PutBucketWebsite',
        's3:DeleteBucketWebsite',
        's3:GetBucketLogging',
        's3:ListAllMyBuckets',
        's3:GetBucketLocation',
        's3:GetBucketTagging',
        's3:PutBucketTagging',
        's3:GetBucketObjectLockConfiguration',
        's3:GetAccelerateConfiguration',
        's3:GetLifecycleConfiguration',
        's3:GetReplicationConfiguration',
        's3:GetBucketRequestPayment',
        // CloudFront
        'cloudfront:CreateDistribution',
        'cloudfront:UpdateDistribution',
        'cloudfront:GetDistribution',
        'cloudfront:ListDistributions',
        'cloudfront:TagResource',
        'cloudfront:ListTagsForResource',
        'cloudfront:CreateOriginAccessControl',
        'cloudfront:GetOriginAccessControl',
        'cloudfront:UpdateOriginAccessControl',
        'cloudfront:DeleteOriginAccessControl',
        'cloudfront:ListOriginAccessControls',
        // Lambda
        'lambda:CreateFunction',
        'lambda:UpdateFunctionCode',
        'lambda:UpdateFunctionConfiguration',
        'lambda:GetFunction',
        'lambda:GetFunctionConfiguration',
        'lambda:GetFunctionUrlConfig',
        'lambda:CreateFunctionUrlConfig',
        'lambda:UpdateFunctionUrlConfig',
        'lambda:PublishVersion',
        'lambda:AddPermission',
        'lambda:RemovePermission',
        'lambda:GetPolicy',
        'lambda:ListVersionsByFunction',
        'lambda:TagResource',
        'lambda:ListTagsForResource',
        // ECR
        'ecr:CreateRepository',
        'ecr:DescribeRepositories',
        'ecr:ListTagsForResource',
        'ecr:TagResource',
        'ecr:PutImageScanningConfiguration',
        'ecr:GetRepositoryPolicy',
        'ecr:PutImageTagMutability',
        // IAM
        'iam:CreateRole',
        'iam:GetRole',
        'iam:PutRolePolicy',
        'iam:GetRolePolicy',
        'iam:DeleteRolePolicy',
        'iam:AttachRolePolicy',
        'iam:DetachRolePolicy',
        'iam:ListRolePolicies',
        'iam:ListAttachedRolePolicies',
        'iam:ListInstanceProfilesForRole',
        'iam:PassRole',
        'iam:TagRole',
        // CloudWatch Logs
        'logs:CreateLogGroup',
        'logs:DescribeLogGroups',
        'logs:ListTagsForResource',
        'logs:TagResource',
        'logs:PutRetentionPolicy',
      ],
      resources: ['*'],
    }));

    // ECR push (deploy backend)
    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'ECRPush',
      actions: [
        'ecr:GetDownloadUrlForLayer',
        'ecr:BatchGetImage',
        'ecr:BatchCheckLayerAvailability',
        'ecr:PutImage',
        'ecr:InitiateLayerUpload',
        'ecr:UploadLayerPart',
        'ecr:CompleteLayerUpload',
      ],
      resources: [
        `arn:aws:ecr:${this.region}:${this.account}:repository/forge-*`,
      ],
    }));

    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'ECRAuth',
      actions: ['ecr:GetAuthorizationToken'],
      resources: ['*'],
    }));

    // S3 frontend deploy
    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'S3FrontendDeploy',
      actions: [
        's3:PutObject',
        's3:GetObject',
        's3:DeleteObject',
        's3:ListBucket',
      ],
      resources: [
        'arn:aws:s3:::forge-*-frontend',
        'arn:aws:s3:::forge-*-frontend/*',
      ],
    }));

    // CloudFront cache invalidation
    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'CloudFrontInvalidation',
      actions: [
        'cloudfront:CreateInvalidation',
        'cloudfront:GetInvalidation',
      ],
      resources: ['*'],
    }));

    // Lambda deploy
    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'LambdaDeploy',
      actions: [
        'lambda:UpdateFunctionCode',
        'lambda:GetFunction',
        'lambda:GetFunctionConfiguration',
        'lambda:PublishVersion',
      ],
      resources: [
        `arn:aws:lambda:${this.region}:${this.account}:function:forge-*`,
      ],
    }));

    // ---------------------------------------------------------------
    // Outputs (matching Terraform outputs)
    // ---------------------------------------------------------------
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      description: 'CloudFront distribution URL',
      value: `https://${distribution.distributionDomainName}`,
    });

    new cdk.CfnOutput(this, 'CloudFrontDomain', {
      description: 'CloudFront distribution domain name (for Cognito callback URLs)',
      value: distribution.distributionDomainName,
    });

    new cdk.CfnOutput(this, 'FunctionUrl', {
      description: 'Lambda function URL',
      value: functionUrl.url,
    });

    new cdk.CfnOutput(this, 'DataBucketName', {
      description: 'S3 data bucket name',
      value: dataBucket.bucketName,
    });

    new cdk.CfnOutput(this, 'FrontendBucketName', {
      description: 'S3 frontend bucket name',
      value: frontendBucket.bucketName,
    });

    new cdk.CfnOutput(this, 'EcrRepositoryUrl', {
      description: 'ECR repository URL for the backend image',
      value: ecrRepository.repositoryUri,
    });

    new cdk.CfnOutput(this, 'CognitoClientId', {
      description: 'Cognito app client ID for the SPA',
      value: userPoolClient.userPoolClientId,
    });

    new cdk.CfnOutput(this, 'GitHubActionsRoleArn', {
      description: 'ARN of the GitHub Actions deploy role (set as AWS_DEPLOY_ROLE_ARN secret)',
      value: githubActionsRole.roleArn,
    });
  }
}
