"""Templated prompt generation and structured-answer parsing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from finrl_eval.schema import Sample

DEFAULT_SYSTEM = (
    "You are a meticulous financial analyst. Answer precisely, show no unnecessary prose, "
    "and always finish with a single JSON object in a ```json code block containing exactly "
    "the requested fields. Use plain numbers (no currency symbols, no thousands separators, "
    "percentages as numbers like 12.5 not 0.125)."
)


def _money(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}"


def _pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


class PromptEngine:
    """Renders Jinja2 templates from a suite's `templates/` directory.

    Templates are selected by task name (`<task>.j2`) with `default.j2` as a fallback.
    """

    def __init__(self, template_dir: Path, system: str = DEFAULT_SYSTEM) -> None:
        self.template_dir = template_dir
        self.system = system
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        self._env.filters["money"] = _money
        self._env.filters["pct"] = _pct

    def render(self, sample: Sample) -> str:
        name = f"{sample.task}.j2"
        if not (self.template_dir / name).exists():
            name = "default.j2"
        template = self._env.get_template(name)
        return template.render(sample=sample, **sample.inputs).strip() + "\n"


_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)
_BARE = re.compile(r"(\{.*\})", re.S)


def parse_json_answer(text: str) -> dict[str, Any] | None:
    """Extract the last JSON object from a model response. Returns None if none parses."""
    candidates = _FENCE.findall(text)
    if not candidates:
        m = _BARE.search(text)
        candidates = [m.group(1)] if m else []
    for raw in reversed(candidates):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None
