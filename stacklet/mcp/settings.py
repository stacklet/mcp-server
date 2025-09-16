from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="stacklet_mcp_")

    assetdb_datasource: Annotated[int, Field(1, description="AssetDB datasource")] = 1


SETTINGS = MCPSettings()
