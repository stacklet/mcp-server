from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server settings."""

    model_config = SettingsConfigDict(env_prefix="stacklet_mcp_")

    assetdb_datasource: int = Field(
        default=1,
        description="AssetDB datasource",
    )
    assetdb_save: bool = Field(
        default=False,
        description="Enable tools that make modifications to AssetDB",
    )


SETTINGS = Settings()
