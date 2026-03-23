import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

interface ForgeStackProps extends cdk.StackProps {
  environment: string;
  domainName?: string;
  acmCertificateArn?: string;
  oidcProviderUrl?: string;
  oidcClientId?: string;
  backendProvisionedConcurrency?: number;
  wsProvisionedConcurrency?: number;
}

export class ForgeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ForgeStackProps) {
    super(scope, id, props);

    const { environment } = props;
    const prefix = `forge-${environment}`;

    // Per-environment config from props (set in app.ts ENV_CONFIG, context override allowed)
    const oidcProviderUrl = props.oidcProviderUrl || '';
    const oidcClientId = props.oidcClientId || '';
    const githubRepo = this.node.tryGetContext('githubRepo') || 'rrm3/forge';
    const domainName = props.domainName || '';
    const acmCertificateArn = props.acmCertificateArn || '';

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
    const ecrRepository = ecr.Repository.fromRepositoryName(
      this, 'BackendRepository', `${prefix}-backend`,
    );

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

    // GSI for querying sessions by type (cross-user)
    sessionsTable.addGlobalSecondaryIndex({
      indexName: 'type-created_at-index',
      partitionKey: { name: 'type', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'created_at', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
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

    // Tips tables
    const tipsTable = new dynamodb.Table(this, 'TipsTable', {
      tableName: `${prefix}-tips`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'tip_id', type: dynamodb.AttributeType.STRING },
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const tipVotesTable = new dynamodb.Table(this, 'TipVotesTable', {
      tableName: `${prefix}-tip-votes`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'tip_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const tipCommentsTable = new dynamodb.Table(this, 'TipCommentsTable', {
      tableName: `${prefix}-tip-comments`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'tip_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'comment_id', type: dynamodb.AttributeType.STRING },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // User ideas table
    const userIdeasTable = new dynamodb.Table(this, 'UserIdeasTable', {
      tableName: `${prefix}-user-ideas`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'idea_id', type: dynamodb.AttributeType.STRING },
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // WebSocket connections table
    const connectionsTable = new dynamodb.Table(this, 'ConnectionsTable', {
      tableName: `${prefix}-connections`,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'connection_id', type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Connections are ephemeral
    });

    // GSI for looking up connections by user_id
    connectionsTable.addGlobalSecondaryIndex({
      indexName: 'user_id-connected_at-index',
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'connected_at', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
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
        `arn:aws:dynamodb:${this.region}:${this.account}:table/forge-*/index/*`,
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
        `arn:aws:bedrock:*::foundation-model/anthropic.claude-*`,
        `arn:aws:bedrock:*::foundation-model/cohere.embed-*`,
        `arn:aws:bedrock:*::foundation-model/cohere.rerank-*`,
        `arn:aws:bedrock:*:${this.account}:inference-profile/us.anthropic.*`,
      ],
    }));

    // Marketplace permissions required for Bedrock model subscriptions
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'MarketplaceAccess',
      actions: [
        'aws-marketplace:ViewSubscriptions',
        'aws-marketplace:Subscribe',
      ],
      resources: ['*'],
    }));

    // SSM Parameter Store access (for OpenAI API key)
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'SSMAccess',
      actions: [
        'ssm:GetParameter',
        'ssm:GetParameters',
      ],
      resources: [
        `arn:aws:ssm:${this.region}:${this.account}:parameter/forge/*`,
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
        OIDC_PROVIDER_URL: oidcProviderUrl,
        OIDC_CLIENT_ID: oidcClientId,
        DYNAMODB_TABLE_PREFIX: prefix,
        AWS_REGION_NAME: this.region,
        S3_BUCKET: dataBucket.bucketName,
        LANCE_BACKEND: 's3',
        LANCE_S3_BUCKET: dataBucket.bucketName,
        LLM_MODEL: 'bedrock/us.anthropic.claude-opus-4-6-v1',
        ORGCHART_S3_KEY: 'orgchart/org-chart.db',
        CONNECTIONS_TABLE: connectionsTable.tableName,
      },
      logGroup,
    });

    // Publish version and create 'live' alias with provisioned concurrency.
    // The deploy workflow updates this alias to new versions on each code deploy.
    // Provisioned concurrency keeps instances pre-initialized to eliminate cold starts.
    const backendPC = props.backendProvisionedConcurrency ?? 10;
    const backendAlias = new lambda.Alias(this, 'BackendLiveAlias', {
      aliasName: 'live',
      version: backendFunction.currentVersion,
      ...(backendPC > 0 ? { provisionedConcurrentExecutions: backendPC } : {}),
    });
    // Override FunctionVersion with SSM dynamic reference so CDK doesn't revert
    // the alias to a stale version on infra-only deploys. The deploy workflow
    // writes the latest version number to SSM after each code deploy.
    // Skip on first deploy (--context skipSsmOverride=true) when SSM params don't exist yet.
    const skipSsmOverride = this.node.tryGetContext('skipSsmOverride') === 'true';
    if (!skipSsmOverride) {
      (backendAlias.node.defaultChild as lambda.CfnAlias).addPropertyOverride(
        'FunctionVersion',
        `{{resolve:ssm:/forge/live-versions/${prefix}-backend}}`,
      );
      // The SSM override breaks the implicit CFn dependency on the version resource.
      // Without this, CFn may create the alias before the version exists (race condition).
      backendAlias.node.addDependency(backendFunction.currentVersion);
    }

    // Function URL on 'live' alias (not $LATEST) so requests hit warm instances
    const functionUrl = backendAlias.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      invokeMode: lambda.InvokeMode.RESPONSE_STREAM,
    });

    // ---------------------------------------------------------------
    // WebSocket Lambda (separate function, same Docker image, raw handler)
    // ---------------------------------------------------------------
    const wsLogGroup = new logs.LogGroup(this, 'WsLogGroup', {
      logGroupName: `/aws/lambda/${prefix}-ws`,
      retention: logs.RetentionDays.TWO_WEEKS,
    });

    // Separate role for WS Lambda to avoid circular dependency with the shared role
    const wsLambdaRole = new iam.Role(this, 'WsLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // WS Lambda needs the same permissions as the backend
    wsLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'DynamoDBAccess',
      actions: [
        'dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem',
        'dynamodb:DeleteItem', 'dynamodb:Query', 'dynamodb:Scan',
        'dynamodb:BatchGetItem', 'dynamodb:BatchWriteItem',
      ],
      resources: [
        `arn:aws:dynamodb:${this.region}:${this.account}:table/forge-*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/forge-*/index/*`,
      ],
    }));
    wsLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'S3Access',
      actions: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:ListBucket'],
      resources: [dataBucket.bucketArn, `${dataBucket.bucketArn}/*`],
    }));
    wsLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'BedrockAccess',
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: [
        `arn:aws:bedrock:*::foundation-model/anthropic.claude-*`,
        `arn:aws:bedrock:*::foundation-model/cohere.embed-*`,
        `arn:aws:bedrock:*:${this.account}:inference-profile/us.anthropic.*`,
      ],
    }));
    wsLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'SSMAccess',
      actions: ['ssm:GetParameter', 'ssm:GetParameters'],
      resources: [`arn:aws:ssm:${this.region}:${this.account}:parameter/forge/*`],
    }));
    wsLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'WebSocketManagementApi',
      actions: ['execute-api:ManageConnections'],
      resources: [`arn:aws:execute-api:${this.region}:${this.account}:*/*`],
    }));

    const wsFunction = new lambda.DockerImageFunction(this, 'WsFunction', {
      functionName: `${prefix}-ws`,
      code: lambda.DockerImageCode.fromEcr(ecrRepository, {
        tagOrDigest: 'latest',
        cmd: ['python', '-m', 'awslambdaric', 'backend.lambda_ws.handler'],
      }),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(900), // 15 min for Worker path
      role: wsLambdaRole,
      environment: {
        OIDC_PROVIDER_URL: oidcProviderUrl,
        OIDC_CLIENT_ID: oidcClientId,
        DYNAMODB_TABLE_PREFIX: prefix,
        AWS_REGION_NAME: this.region,
        S3_BUCKET: dataBucket.bucketName,
        LANCE_BACKEND: 's3',
        LANCE_S3_BUCKET: dataBucket.bucketName,
        LLM_MODEL: 'bedrock/us.anthropic.claude-opus-4-6-v1',
        ORGCHART_S3_KEY: 'orgchart/org-chart.db',
        CONNECTIONS_TABLE: connectionsTable.tableName,
        LAMBDA_FUNCTION_NAME: `${prefix}-ws:live`, // self-invoke targets alias for warm instances
      },
      logGroup: wsLogGroup,
    });

    // Publish version and create 'live' alias with provisioned concurrency
    const wsPC = props.wsProvisionedConcurrency ?? 20;
    const wsAlias = new lambda.Alias(this, 'WsLiveAlias', {
      aliasName: 'live',
      version: wsFunction.currentVersion,
      ...(wsPC > 0 ? { provisionedConcurrentExecutions: wsPC } : {}),
    });
    if (!skipSsmOverride) {
      (wsAlias.node.defaultChild as lambda.CfnAlias).addPropertyOverride(
        'FunctionVersion',
        `{{resolve:ssm:/forge/live-versions/${prefix}-ws}}`,
      );
      wsAlias.node.addDependency(wsFunction.currentVersion);
    }

    // Grant WS Lambda permission to invoke itself (Dispatcher -> Worker)
    wsLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'SelfInvoke',
      actions: ['lambda:InvokeFunction'],
      resources: [
        `arn:aws:lambda:${this.region}:${this.account}:function:${prefix}-ws`,
        `arn:aws:lambda:${this.region}:${this.account}:function:${prefix}-ws:*`,
      ],
    }));

    // ---------------------------------------------------------------
    // API Gateway WebSocket API
    // ---------------------------------------------------------------
    const wsApi = new apigatewayv2.CfnApi(this, 'WebSocketApi', {
      name: `${prefix}-ws`,
      protocolType: 'WEBSOCKET',
      routeSelectionExpression: '$request.body.action',
    });

    // Lambda integration for WebSocket routes (points to WS Lambda, not backend)
    const wsIntegration = new apigatewayv2.CfnIntegration(this, 'WsIntegration', {
      apiId: wsApi.ref,
      integrationType: 'AWS_PROXY',
      integrationUri: `arn:aws:apigateway:${this.region}:lambda:path/2015-03-31/functions/${wsAlias.functionArn}/invocations`,
    });

    // $connect route
    new apigatewayv2.CfnRoute(this, 'ConnectRoute', {
      apiId: wsApi.ref,
      routeKey: '$connect',
      target: `integrations/${wsIntegration.ref}`,
    });

    // $disconnect route
    new apigatewayv2.CfnRoute(this, 'DisconnectRoute', {
      apiId: wsApi.ref,
      routeKey: '$disconnect',
      target: `integrations/${wsIntegration.ref}`,
    });

    // $default route
    new apigatewayv2.CfnRoute(this, 'DefaultRoute', {
      apiId: wsApi.ref,
      routeKey: '$default',
      target: `integrations/${wsIntegration.ref}`,
    });

    // Deploy the WebSocket API
    const wsDeployment = new apigatewayv2.CfnDeployment(this, 'WsDeployment', {
      apiId: wsApi.ref,
    });
    wsDeployment.addDependency(
      this.node.findChild('ConnectRoute') as cdk.CfnResource
    );

    const wsStage = new apigatewayv2.CfnStage(this, 'WsStage', {
      apiId: wsApi.ref,
      stageName: 'v1',
      autoDeploy: true,  // API Gateway creates deployments automatically; deploymentId is incompatible
    });

    // Grant API Gateway permission to invoke WS Lambda
    wsAlias.addPermission('WsApiGatewayInvoke', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      sourceArn: `arn:aws:execute-api:${this.region}:${this.account}:${wsApi.ref}/*`,
    });

    // WebSocket ManageConnections permission is on wsLambdaRole (above)

    // Add WebSocket endpoint to WS Lambda environment.
    // Use Fn.join to avoid a circular dependency (wsFunction -> wsApi -> wsFunction).
    wsFunction.addEnvironment(
      'WEBSOCKET_API_ENDPOINT',
      cdk.Fn.join('', [
        'https://', wsApi.ref, '.execute-api.', this.region, '.amazonaws.com/v1',
      ]),
    );

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
    const lambdaOrigin = new origins.FunctionUrlOrigin(functionUrl, {});

    // Build optional custom domain configuration
    const certificate = acmCertificateArn
      ? acm.Certificate.fromCertificateArn(this, 'Certificate', acmCertificateArn)
      : undefined;

    // Security response headers (CSP, HSTS, clickjacking, MIME sniffing)
    const securityHeaders = new cloudfront.ResponseHeadersPolicy(this, 'SecurityHeaders', {
      responseHeadersPolicyName: `${prefix}-security-headers`,
      securityHeadersBehavior: {
        contentTypeOptions: { override: true },
        frameOptions: {
          frameOption: cloudfront.HeadersFrameOption.DENY,
          override: true,
        },
        strictTransportSecurity: {
          accessControlMaxAge: cdk.Duration.seconds(31536000),
          includeSubdomains: true,
          override: true,
        },
      },
      customHeadersBehavior: {
        customHeaders: [
          {
            header: 'Content-Security-Policy',
            override: true,
            value: [
              "default-src 'self'",
              "script-src 'self'",
              "style-src 'self' 'unsafe-inline' https://api.fontshare.com https://fonts.googleapis.com",
              "font-src 'self' https://cdn.fontshare.com https://fonts.gstatic.com",
              "img-src 'self' data: https://media-process.hibob.com",
              `connect-src 'self'${oidcProviderUrl ? ` ${oidcProviderUrl}` : ''} wss:`,
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "frame-ancestors 'none'",
            ].join('; '),
          },
        ],
      },
    });

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
        responseHeadersPolicy: securityHeaders,
      },

      additionalBehaviors: {
        '/api/*': {
          origin: lambdaOrigin,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          compress: true,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
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
    const githubOidcProvider = iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
      this, 'GitHubActionsOIDC',
      `arn:aws:iam::${this.account}:oidc-provider/token.actions.githubusercontent.com`,
    );

    const githubActionsRole = new iam.Role(this, 'GitHubActionsRole', {
      roleName: `${prefix}-github-actions`,
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

    // CDK resource management
    githubActionsRole.addToPolicy(new iam.PolicyStatement({
      sid: 'CDKResourceManagement',
      actions: [
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
        // CloudFormation (CDK deploy)
        'cloudformation:CreateStack',
        'cloudformation:UpdateStack',
        'cloudformation:DeleteStack',
        'cloudformation:DescribeStacks',
        'cloudformation:DescribeStackEvents',
        'cloudformation:GetTemplate',
        'cloudformation:CreateChangeSet',
        'cloudformation:DescribeChangeSet',
        'cloudformation:ExecuteChangeSet',
        'cloudformation:DeleteChangeSet',
        'cloudformation:GetTemplateSummary',
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
        'cloudfront:CreateResponseHeadersPolicy',
        'cloudfront:GetResponseHeadersPolicy',
        'cloudfront:UpdateResponseHeadersPolicy',
        'cloudfront:DeleteResponseHeadersPolicy',
        'cloudfront:ListResponseHeadersPolicies',
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
        'lambda:CreateAlias',
        'lambda:UpdateAlias',
        'lambda:GetAlias',
        'lambda:DeleteAlias',
        'lambda:PutProvisionedConcurrencyConfig',
        'lambda:GetProvisionedConcurrencyConfig',
        'lambda:DeleteProvisionedConcurrencyConfig',
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
        // API Gateway
        'apigateway:*',
        'execute-api:*',
        // SSM
        'ssm:GetParameter',
        'ssm:PutParameter',
        'ssm:DeleteParameter',
        'ssm:DescribeParameters',
        'ssm:ListTagsForResource',
        'ssm:AddTagsToResource',
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
        'lambda:CreateAlias',
        'lambda:UpdateAlias',
        'lambda:GetAlias',
        'lambda:GetProvisionedConcurrencyConfig',
      ],
      resources: [
        `arn:aws:lambda:${this.region}:${this.account}:function:forge-*`,
      ],
    }));

    // ---------------------------------------------------------------
    // Outputs
    // ---------------------------------------------------------------
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      description: 'CloudFront distribution URL',
      value: `https://${distribution.distributionDomainName}`,
    });

    new cdk.CfnOutput(this, 'CloudFrontDomain', {
      description: 'CloudFront distribution domain name (for OIDC callback URLs)',
      value: distribution.distributionDomainName,
    });

    new cdk.CfnOutput(this, 'FunctionUrl', {
      description: 'Lambda function URL',
      value: functionUrl.url,
    });

    new cdk.CfnOutput(this, 'WebSocketApiUrl', {
      description: 'WebSocket API endpoint',
      value: `wss://${wsApi.ref}.execute-api.${this.region}.amazonaws.com/${wsStage.stageName}`,
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

    new cdk.CfnOutput(this, 'GitHubActionsRoleArn', {
      description: 'ARN of the GitHub Actions deploy role (set as AWS_DEPLOY_ROLE_ARN secret)',
      value: githubActionsRole.roleArn,
    });
  }
}
