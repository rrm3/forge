import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _get_ssm_parameter(name: str) -> str:
    """Fetch a parameter from SSM Parameter Store. Returns empty string on failure."""
    try:
        import boto3

        client = boto3.client("ssm")
        resp = client.get_parameter(Name=name, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception:
        logger.warning("Failed to load SSM parameter %s", name)
        return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Auth (OIDC / Digital Science ID)
    oidc_provider_url: str = ""
    oidc_client_id: str = ""

    # DynamoDB
    dynamodb_table_prefix: str = "forge"
    aws_region: str = "us-east-1"

    # S3
    s3_bucket: str = "forge-local"

    # LanceDB
    lance_backend: str = "local"  # "s3" | "local"
    lance_local_path: str = "/tmp/lance"
    lance_s3_bucket: str = ""

    # LLM
    llm_model: str = "bedrock/global.anthropic.claude-opus-4-6-v1"
    bedrock_access_key_id: str = ""
    bedrock_secret_access_key: str = ""
    bedrock_role_arn: str = ""  # cross-account role for Bedrock (preferred over static keys)

    # Gemini (speech-to-text transcription)
    gemini_api_key: str = ""

    # Org chart
    orgchart_s3_key: str = "orgchart/org-chart.db"
    orgchart_local_path: str = ""

    # WebSocket (production - API Gateway)
    connections_table: str = ""
    websocket_api_endpoint: str = ""
    lambda_function_name: str = ""  # for Dispatcher self-invoke

    # PostHog analytics (empty key = disabled, e.g. in dev)
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"

    # Allowed email domains config (JSON file on S3 or local)
    allowed_domains_s3_key: str = "config/allowed-domains.json"
    allowed_domains_local_path: str = ""

    # Dev
    dev_mode: bool = False


settings = Settings()

# Load secrets from SSM in production (when env vars aren't set)
if not settings.gemini_api_key and not settings.dev_mode:
    settings.gemini_api_key = _get_ssm_parameter("/forge/gemini-api-key")
if not settings.posthog_api_key and not settings.dev_mode:
    settings.posthog_api_key = _get_ssm_parameter("/forge/posthog-api-key")
