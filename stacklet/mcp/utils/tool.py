# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from typing import Any, Callable

from fastmcp.tools import Tool
from pydantic import BaseModel

from mcp.types import ToolAnnotations


def make_tool(
    fn: Callable[..., Any],
    *,
    read_only: bool,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = True,
    output_schema: dict[str, Any] | None = None,
) -> Tool:
    """
    Build a Tool from a function, with behavioural annotations attached.

    Hosts show these hints to the user when they ask to approve a tool call, so
    that a call which can change or destroy state doesn't look like a read.

    `destructive` and `idempotent` only carry meaning for tools that aren't
    read-only, but they're always sent: the spec defaults `destructiveHint` to
    true, and a host that doesn't check `readOnlyHint` first shouldn't be told
    that our read tools are destructive.

    `output_schema` is for tools that build their own ToolResult: fastmcp derives
    a schema from the return annotation, which for those says only ToolResult, so
    pass the real one rather than leaving clients without any.
    """
    annotations = ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )
    if output_schema is None:
        return Tool.from_function(fn, annotations=annotations)
    return Tool.from_function(fn, annotations=annotations, output_schema=output_schema)


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
