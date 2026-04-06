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
  backendProvisionedConcurrency: number;
  wsProvisionedConcurrency: number;
  posthogApiKey: string;
  devMode?: boolean;
}> = {
  production: {
    domainName: 'aituesdays.digitalscience.ai',
    acmCertificateArn: 'arn:aws:acm:us-east-1:887690967243:certificate/3c05f20c-617f-4dcf-8958-374b3c09770d',
    oidcProviderUrl: 'https://id.digitalscience.ai',
    oidcClientId: '0bfe6d8ddb94027981248d2a0bd21991',
    backendProvisionedConcurrency: 10,
    wsProvisionedConcurrency: 20,
    posthogApiKey: 'phc_Qn6PGsXODJxvYCMV8Vv099fYpf9oAi1OPctdvgwb828',
  },
  staging: {
    domainName: 'aituesdays-staging.digitalscience.ai',
    acmCertificateArn: 'arn:aws:acm:us-east-1:887690967243:certificate/25bf51b4-4b07-42b7-8d97-c87be6f06c48',
    oidcProviderUrl: 'https://id-staging.digitalscience.ai',
    oidcClientId: 'bf985c39ba613a31ddce92186bb374f8',
    backendProvisionedConcurrency: 0,
    wsProvisionedConcurrency: 0,
    posthogApiKey: 'phc_7wUFuz56pMvIhqnSalLqHakMDY2PKeT4KIM1NZHFQpB',
    devMode: true,
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
  backendProvisionedConcurrency: envConfig?.backendProvisionedConcurrency ?? 0,
  wsProvisionedConcurrency: envConfig?.wsProvisionedConcurrency ?? 0,
  posthogApiKey: envConfig?.posthogApiKey || '',
  devMode: envConfig?.devMode ?? false,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
});
