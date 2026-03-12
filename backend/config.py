from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Auth
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

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
    llm_model: str = "anthropic/claude-sonnet-4-20250514"

    # Dev
    dev_mode: bool = False


settings = Settings()
