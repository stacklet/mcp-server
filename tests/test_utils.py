from stacklet.mcp.utils import get_package_file


class TestGetPackageFile:
    def test_exists(self):
        doc = get_package_file("platform/graphql_info.md")
        assert doc.exists()
        assert "Stacklet GraphQL API Overview" in doc.read_text()

    def test_unknown(self):
        unknown = get_package_file("not/here")
        assert not unknown.exists()
