# Lambda Alias Versioning & Zero-Downtime Deploys

This document covers the full Lambda deployment architecture: how code deploys
and CDK deploys interact, the SSM override pattern that prevents version drift,
and the zero-downtime pre-warming strategy.

## Two Deployment Paths

There are two independent ways Lambda configuration changes:

**Code deploys** (GitHub Actions, automatic on push to main):
* Builds a Docker image, pushes to ECR
* Calls `update-function-code --publish` - updates `$LATEST` code, publishes a new numbered version
* Pre-warms the new version with provisioned concurrency
* Swings the `live` alias to the warm version
* Records the version in SSM for CDK

**CDK deploys** (manual, run when infrastructure changes):
* Updates the Lambda *function definition* on `$LATEST` (env vars, memory, timeout, etc.)
* Does NOT publish a new version or swing the alias
* The alias stays on whatever version SSM says

**Critical implication:** Code deploys don't touch env vars. CDK deploys don't publish
versions. A new env var added in CDK only reaches production after BOTH a CDK deploy
(to update `$LATEST` config) AND a code deploy (to publish a version from that config).

### Environment Variables

Lambda env vars (OIDC_PROVIDER_URL, OIDC_CLIENT_ID, etc.) are set by CDK in
`infrastructure/cdk/bin/app.ts` via `ENV_CONFIG`. They are baked into `$LATEST` when
`cdk deploy` runs. When the code deploy workflow calls `update-function-code --publish`,
the new version inherits whatever env vars are on `$LATEST` at that moment.

If a CDK deploy sets wrong/empty env vars on `$LATEST`, every subsequent code deploy
will publish versions with those wrong values. This is how empty OIDC vars caused a
production outage on 2026-03-22.

## The SSM Override Pattern

### The Problem

CDK's `lambda.Alias` with `version: fn.currentVersion` creates a `AWS::Lambda::Version`
resource at synth time. The alias in the CloudFormation template is hardwired to that version.

The code deploy workflow publishes new versions and swings the alias on every push. This
creates version drift: CDK thinks the alias should point to version N (from last CDK deploy),
but the workflow has since moved it to version N+5.

If a CDK deploy touches the Lambda function definition (env var, memory, etc.),
CloudFormation reverts the alias to the stale CDK-computed version. This breaks production.

### The Solution

Override the CloudFormation `FunctionVersion` property with an SSM dynamic reference:

```typescript
const backendAlias = new lambda.Alias(this, 'BackendLiveAlias', {
  aliasName: 'live',
  version: backendFunction.currentVersion,  // CDK requires this, but we override below
  provisionedConcurrentExecutions: 10,
});

// Override so CDK doesn't revert the alias to a stale version on infra deploys.
// The deploy workflow writes the latest version number to SSM after each code deploy.
(backendAlias.node.defaultChild as lambda.CfnAlias).addPropertyOverride(
  'FunctionVersion',
  `{{resolve:ssm:/forge/live-versions/${prefix}-backend}}`,
);
```

The deploy workflow writes the version to SSM after each alias update:

```bash
aws ssm put-parameter \
  --name "/forge/live-versions/${FUNCTION_NAME}" \
  --value "${VERSION}" --type String --overwrite
```

CloudFormation resolves `{{resolve:ssm:...}}` at deploy time, so it always gets
the version the workflow last deployed.

### SSM Parameters

* `/forge/live-versions/forge-production-backend` - current REST Lambda alias version
* `/forge/live-versions/forge-production-ws` - current WS Lambda alias version

## Zero-Downtime Deploy Flow

The deploy workflow pre-warms new Lambda versions before swinging the alias.
This eliminates cold starts during deploys. The flow is **fail-closed**: if
pre-warming fails, the alias is NOT swung and the deploy aborts.

```
1. update-function-code --publish         → new version created
2. put-provisioned-concurrency-config     → start pre-warming new version
3. poll until version PC is READY         → new version is warm
   (if FAILED or timeout: abort, do NOT swing alias)
4. delete-provisioned-concurrency-config  → remove version-level PC (see note below)
5. update-alias --name live               → traffic shifts to pre-warmed version
6. ssm put-parameter                      → record version for CDK
7. poll until alias PC is READY           → alias PC initializes on new version
```

### Why delete version PC before swinging the alias? (Step 4)

AWS does not allow an alias with provisioned concurrency to point to a version that
also has its own provisioned concurrency. The `update-alias` call will fail with
`ResourceConflictException`. We must delete version-level PC first.

The warm execution environments persist briefly after PC deletion (they become
available as on-demand instances). Swinging the alias immediately after ensures
the alias-level PC can reuse those warm environments.

### Why fail-closed?

If the pre-warm step fails (capacity limit, account quota, bad function code) and
we swing the alias anyway, users hit cold starts (5-15 seconds for Docker images).
Better to abort and keep traffic on the old working version.

### Temporary double provisioned concurrency

During steps 2-4, both the old version (via alias) and new version (directly) have
provisioned concurrency active. This briefly doubles the PC count:
* REST Lambda: 10 + 10 = 20 during transition
* WS Lambda: 20 + 20 = 40 during transition

This lasts ~60 seconds while the new version warms up. If it exceeds account limits,
the pre-warm will fail and the deploy will abort safely.

## Rules

* **NEVER** create a `lambda.Alias` with `version: fn.currentVersion` without the
  SSM override. CDK's `currentVersion` goes stale as soon as the deploy workflow
  publishes a new version.
* **NEVER** remove the `addPropertyOverride` calls from the alias definitions.
  Without them, CDK will revert the alias on the next infra deploy.
* **NEVER** manually update the SSM parameters or the `live` alias. The deploy
  workflow is the single source of truth.
* **NEVER** manually call `update-function-configuration` on production Lambdas.
  Use CDK to change env vars, memory, etc.
* The `version: backendFunction.currentVersion` property in the Alias construct
  is required by CDK's type system but has no effect at deploy time (the override
  replaces it in the CloudFormation template). Do not remove it.

## Deploying Infrastructure Changes

When you change CDK files (env vars, IAM, new resources, etc.):

1. Run `cdk deploy` for the affected environment to apply infra changes
2. Push to main to trigger the code deploy workflow
3. The workflow publishes a new version from the updated `$LATEST`

The pre-push hook warns when CDK files changed as a reminder to run `cdk deploy`.
After running `cdk deploy`, use `git push --no-verify` since the hook only checks
git diffs, not deployed state.

## Troubleshooting

**Deploy aborted with "Pre-warm failed":**
Check the StatusReason in the GitHub Actions log. Common causes:
* Account provisioned concurrency limit exceeded
* Function code fails to initialize (import error, missing dependency)
* Insufficient unreserved concurrent execution quota

**Auth broken after CDK deploy (empty OIDC vars):**
Verify `ENV_CONFIG` in `app.ts` has the correct OIDC values for the environment.
CDK reads env vars from `ENV_CONFIG`, not from CDK context. If values are wrong,
fix `app.ts`, re-run `cdk deploy`, then trigger a code deploy.

**Alias pointing to wrong version:**
Check SSM: `aws ssm get-parameter --name /forge/live-versions/FUNCTION_NAME`
Check alias: `aws lambda get-alias --function-name NAME --name live`
These should match. If not, re-run the deploy workflow (push a commit).
Do NOT manually update the alias or SSM parameter.
