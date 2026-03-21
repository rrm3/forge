from pydantic_settings import BaseSettings, SettingsConfigDict


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
    llm_model: str = "bedrock/us.anthropic.claude-opus-4-6-v1"
    bedrock_access_key_id: str = ""
    bedrock_secret_access_key: str = ""

    # Gemini (speech-to-text transcription)
    gemini_api_key: str = ""

    # Org chart
    orgchart_s3_key: str = "orgchart/org-chart.db"
    orgchart_local_path: str = ""

    # WebSocket (production - API Gateway)
    connections_table: str = ""
    websocket_api_endpoint: str = ""
    lambda_function_name: str = ""  # for Dispatcher self-invoke

    # Dev
    dev_mode: bool = False


settings = Settings()
