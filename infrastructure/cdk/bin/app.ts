#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { ForgeStack } from '../lib/forge-stack';

const app = new cdk.App();

const environment = app.node.tryGetContext('env') || 'dev';

// Per-environment defaults so `cdk deploy` always gets the right config
// without needing to pass --context flags manually.
const ENV_CONFIG: Record<string, {
  domainName: string;
  acmCertificateArn: string;
  oidcProviderUrl: string;
  oidcClientId: string;
}> = {
  production: {
    domainName: 'aituesday.digitalscience.ai',
    acmCertificateArn: 'arn:aws:acm:us-east-1:887690967243:certificate/9af158db-48c5-43b4-a0d7-61ce2db15b89',
    oidcProviderUrl: 'https://id.digitalscience.ai',
    oidcClientId: '0bfe6d8ddb94027981248d2a0bd21991',
  },
  staging: {
    domainName: 'aituesday-staging.digitalscience.ai',
    acmCertificateArn: 'arn:aws:acm:us-east-1:887690967243:certificate/e08087ef-0495-4364-b960-91aa02c8a97c',
    oidcProviderUrl: 'https://id.digitalscience.ai',
    oidcClientId: '40656eed824af4e6ebeaca1f99740bcc',
  },
};

const envConfig = ENV_CONFIG[environment];

new ForgeStack(app, `forge-${environment}`, {
  environment,
  // Pass per-environment config as props (context overrides allowed for ad-hoc deploys)
  domainName: app.node.tryGetContext('domainName') || envConfig?.domainName || '',
  acmCertificateArn: app.node.tryGetContext('acmCertificateArn') || envConfig?.acmCertificateArn || '',
  oidcProviderUrl: app.node.tryGetContext('oidcProviderUrl') || envConfig?.oidcProviderUrl || '',
  oidcClientId: app.node.tryGetContext('oidcClientId') || envConfig?.oidcClientId || '',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
});
