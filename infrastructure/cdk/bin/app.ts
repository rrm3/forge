#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { ForgeStack } from '../lib/forge-stack';

const app = new cdk.App();

const environment = app.node.tryGetContext('env') || 'dev';

// Per-environment defaults so `cdk deploy` always gets the right domain/cert
// without needing to pass --context flags manually.
const ENV_CONFIG: Record<string, { domainName: string; acmCertificateArn: string }> = {
  production: {
    domainName: 'aituesday.digitalscience.ai',
    acmCertificateArn: 'arn:aws:acm:us-east-1:887690967243:certificate/9af158db-48c5-43b4-a0d7-61ce2db15b89',
  },
  staging: {
    domainName: 'aituesday-staging.digitalscience.ai',
    acmCertificateArn: 'arn:aws:acm:us-east-1:887690967243:certificate/e08087ef-0495-4364-b960-91aa02c8a97c',
  },
};

const envConfig = ENV_CONFIG[environment];

new ForgeStack(app, `forge-${environment}`, {
  environment,
  // Pass domain/cert as context so the stack picks them up automatically
  domainName: app.node.tryGetContext('domainName') || envConfig?.domainName || '',
  acmCertificateArn: app.node.tryGetContext('acmCertificateArn') || envConfig?.acmCertificateArn || '',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
});
