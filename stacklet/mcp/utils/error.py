# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

"""
Error handling utilities for creating annotated ToolErrors with user guidance.
"""

from fastmcp.exceptions import ToolError


def annotated_error(
    problem: str,
    likely_cause: str,
    next_steps: str,
    original_error: str | None = None,
) -> ToolError:
    """
    Create a well-annotated ToolError with context and guidance.

    Args:
        problem: Clear description of what went wrong
        likely_cause: Most probable reason for the failure
        next_steps: Actionable advice for resolving the issue
        original_error: Optional underlying error details

    Returns:
        ToolError with structured message including context and guidance
    """
    message = f"{problem}. This likely means {likely_cause}. Next steps: {next_steps}"
    if original_error:
        message += f". Original error: {original_error}"
    return ToolError(message)
