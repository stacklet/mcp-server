import tempfile

from pathlib import Path
from typing import IO, Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server settings."""

    model_config = SettingsConfigDict(
        env_prefix="stacklet_mcp_",
        validate_assignment=True,
    )

    downloads_path: Path = Field(default_factory=lambda: Path(tempfile.gettempdir()))

    assetdb_datasource: int = Field(
        default=1,
        description="AssetDB datasource",
    )
    assetdb_allow_save: bool = Field(
        default=False,
        description="Enable tools that make modifications to AssetDB",
    )
    assetdb_allow_archive: bool = Field(
        default=False,
        description="Enable query archiving functionality in AssetDB",
    )
    platform_allow_mutations: bool = Field(
        default=False,
        description="Enable calling mutations in the Platform GraphQL API",
    )

    def download_file(self, mode: str, prefix: str, suffix: str) -> IO[Any]:
        self.downloads_path.mkdir(parents=True, exist_ok=True)
        return tempfile.NamedTemporaryFile(
            mode=mode,
            dir=str(self.downloads_path),
            prefix=prefix,
            suffix=suffix,
            delete=False,
        )


SETTINGS = Settings()
