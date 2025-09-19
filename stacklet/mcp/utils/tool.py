from pydantic import BaseModel


class ToolsetInfo(BaseModel):
    """ "Info about a toolset."""

    meta: dict[str, str]
    content: str


def info_tool_result(content: str) -> ToolsetInfo:
    """
    Attempt to bump the perceived importance of the steering information we send.
    """
    return ToolsetInfo(
        content=content,
        meta={
            "importance": "critical",
            "memorability": "high",
            "priority": "top",
        },
    )
