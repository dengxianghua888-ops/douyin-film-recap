"""Derived render contracts. These records never own or edit a storyboard."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
from typing import Any, Mapping

PLAN_SCHEMA = "film-render-plan/1"
CACHE_SCHEMA = "film-segment-cache/1"
PLANNER_REVISION = "segment-av-planner/1"
RENDERER_REVISION = "segment-av-renderer/3"
ROUNDING_REVISION = "cumulative-nearest-half-up/1"
CHECKER_REVISION = "full-decode-av/1"


class RenderContractError(ValueError):
    """An input or realized output cannot safely meet the derived contract."""


def rational(value: Any) -> Fraction:
    """Interpret original decimal values, never binary float approximations."""
    if isinstance(value, bool):
        raise RenderContractError("BOOLEAN_IS_NOT_A_CLOCK")
    try:
        if isinstance(value, Mapping):
            if any(type(value[key]) is not int for key in ("num", "den")):
                raise RenderContractError("NON_INTEGER_RATIONAL_COMPONENT")
            result = Fraction(value["num"], value["den"])
        elif isinstance(value, Fraction):
            result = value
        else:
            result = Fraction(str(value))
    except (ValueError, TypeError, ZeroDivisionError, KeyError, OverflowError) as exc:
        raise RenderContractError("INVALID_RATIONAL_CLOCK") from exc
    return result


def ratio(value: Any) -> dict[str, int]:
    value = rational(value)
    return {"num": value.numerator, "den": value.denominator}


def quantize(value: Any) -> int:
    value = rational(value)
    if value < 0:
        return -quantize(-value)
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def _canonical(value: Any) -> Any:
    if isinstance(value, Fraction):
        return ratio(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RenderContractError("NON_FINITE_PARAMETER")
        return ratio(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise RenderContractError("NON_STRING_PARAMETER_KEY")
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise RenderContractError(f"UNSUPPORTED_PARAMETER: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_sha(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise RenderContractError("INVALID_SHA256")
    return value


def content_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    """Only verified byte identity enters media keys; locators never do."""
    size = value.get("size", value.get("size_bytes"))
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise RenderContractError("INVALID_CONTENT_SIZE")
    return {"sha256": validate_sha(value.get("sha256")), "size": size}


def authority_payload(storyboard: Any) -> dict[str, Any]:
    value = storyboard.model_dump(mode="json")
    value.pop("output", None)
    for segment in value.get("segments", []):
        for name in ("status", "rendered_file", "rendered_duration_sec"):
            segment.pop(name, None)
    return value
