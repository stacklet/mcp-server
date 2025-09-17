import pytest

from stacklet.mcp.platform.graphql import has_mutations


class TestHasMutations:
    @pytest.mark.parametrize(
        "query", ["query { foo bar }", "query Baz { foo bar }", "query { foo } query { bar }"]
    )
    def test_no_mutations(self, query: str):
        assert not has_mutations(query)

    @pytest.mark.parametrize(
        "query",
        [
            "mutation { foo(x: Number) { foo bar } }",
            "mutation Baz { foo(x: Number) { foo bar } }",
            "mutation { foo(x: Int) { bar } baz(y: Boolean) { bza } }",
            "mutation { foo(x: Int) { bar } } mutation { baz(y: Boolean) { bza } }",
            "query { foo } mutation { bar(x: Boolean) { baz } }",
        ],
    )
    def test_with_mutations(self, query: str):
        assert has_mutations(query)
