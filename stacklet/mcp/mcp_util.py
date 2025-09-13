import json

from functools import wraps
from inspect import get_annotations
from typing import Annotated, Any, Callable

from fastmcp.utilities.types import is_class_member_of_type
from pydantic import BeforeValidator


def json_guard(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    https://github.com/jlowin/fastmcp/issues/932

    It turns out that Claude Code in particular, but other reported LLMs too, have
    some difficulty resisting the temptation to JSON-encode arbitrary arguments.

    This decorator hacks up the function signature of a potential mcp.tool so as to
    advertise support for strings in any argument that doesn't already support them;
    and then, when they're delivered, try to load the JSON before handing on to the
    actual implementation, so that can continue to see the originally-intended types.

    It's probably wise to decorate any tools which take non-str arguments with this.
    """
    guarded = {k: _json_guard(v) for k, v in get_annotations(fn).items()}

    @wraps(fn)
    def wrapped(**kwargs: Any) -> Any:
        return fn(**kwargs)

    wrapped.__annotations__ = guarded
    return wrapped


def _json_guard(typ: Any) -> Any:
    # If a string is a legitimate argument type, nothing we can/should do.
    if is_class_member_of_type(typ, str):
        return typ

    # If it's not, ensure it's annotated with a BeforeValidator which can
    # both load JSON if/when delivered _and_ advertise the str type in the
    # json schema used to validate the tool call in the mcp SDK.
    return Annotated[typ, BeforeValidator(_maybe_load_json, typ | str)]


def _maybe_load_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value) if value else None
    return value
