# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import tempfile

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server settings."""

    model_config = SettingsConfigDict(
        env_prefix="stacklet_mcp_",
        validate_assignment=True,
    )

    downloads_path: Path = Field(default_factory=lambda: Path(tempfile.gettempdir()))
    downloads_enabled: bool = Field(
        default=True,
        description=(
            "Write complete query results to downloads_path. Disable for hosted "
            "deployments, where the caller cannot read the server's filesystem and "
            "the files would accumulate unbounded; full results are then attached "
            "to the tool response instead."
        ),
    )

    assetdb_datasource: int | None = Field(
        default=None,
        description=(
            "Redash data source id to query, for a deployment that needs to name one "
            "explicitly. Left unset, the id is looked up by name -- see "
            "assetdb_datasource_name -- which is what every Stacklet deployment wants: "
            "Redash assigns the id at creation, so it differs between deployments and "
            "cannot be assumed."
        ),
    )
    assetdb_datasource_name: str = Field(
        default="AssetDB",
        description=(
            "Name of the Redash data source to resolve an id from, used when "
            "assetdb_datasource is unset. Matches the name Stacklet provisions, which "
            "is stable across deployments in the way the id is not."
        ),
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


SETTINGS = Settings()
