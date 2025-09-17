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
            "mutation { foo(x: Number) { bar } baz(y: Bool) { bza } }",
            "mutation { foo(x: Number) { bar } } mutation { baz(y: Bool) { bza } }",
        ],
    )
    def test_with_mutations(self, query: str):
        assert has_mutations(query)
