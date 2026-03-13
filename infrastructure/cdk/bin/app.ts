#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { ForgeStack } from '../lib/forge-stack';

const app = new cdk.App();

const environment = app.node.tryGetContext('env') || 'dev';

new ForgeStack(app, `forge-${environment}`, {
  environment,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
});
