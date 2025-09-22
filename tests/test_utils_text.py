# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

import pytest

from stacklet.mcp.utils.text import get_file_text


class TestGetFileTest:
    def test_exists(self):
        doc = get_file_text("platform/graphql_info.md")
        assert "Stacklet GraphQL API Overview" in doc

    def test_unknown(self):
        with pytest.raises(Exception):
            get_file_text("not/here")
