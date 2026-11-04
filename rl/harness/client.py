"""The one model client: every model call in the repo (API runner, judge, probes) goes through `stream`.

  - one streamed request, following pause_turn continuations in the same container
  - jittered backoff on rate limits, overload and connection errors, never past the caller's deadline
  - usage in one shape (USAGE_KEYS, cache tokens included), summed over continuations
  - the served model must be the requested one; no silent fallback

This is the only module that imports a provider SDK. A built task copies it beside judge.py, so the
verifier's judge calls go through it too.
"""

from __future__ import annotations

import pathlib
import random
import time

import anthropic
import httpx

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
CODE_EXECUTION = {"type": "code_execution_20260521", "name": "code_execution"}
FILES_BETA = "files-api-2025-04-14"
SKILLS_BETA = "code-execution-2025-08-25"
MAX_CONTINUATIONS = 40
TRIES = 6
# `read` is the longest gap allowed between streamed bytes; the server sends keepalive pings while
# code runs, so a gap this long means a stalled connection, not a slow task.
HTTP_TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=120.0, pool=30.0)
TRANSIENT = (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)


class DeadlineExceeded(RuntimeError):
    pass


class ServedModelMismatch(RuntimeError):
    pass


def connect():
    return anthropic.Anthropic(max_retries=0, timeout=HTTP_TIMEOUT)


def upload(api, files: dict[str, bytes]) -> list[str]:
    """Upload files for the code-execution container; returns their ids."""
    return [api.beta.files.upload(file=(name, data, "text/plain")).id for name, data in files.items()]


def delete(api, file_ids: list[str]) -> None:
    for f in file_ids:
        try:
            api.beta.files.delete(f)
        except anthropic.APIError:
            pass


def generated_pngs(api, content: list) -> dict[str, bytes]:
    """{file name: bytes} of the PNGs the code-execution sandbox produced during a turn."""
    out = {}
    for block in content:
        if block.type != "bash_code_execution_tool_result" or block.content.type != "bash_code_execution_result":
            continue
        for ref in block.content.content or []:
            if ref.type != "bash_code_execution_output":
                continue
            name = pathlib.PurePosixPath(api.beta.files.retrieve_metadata(ref.file_id).filename).name
            if name.endswith(".png"):
                out[name] = api.beta.files.download(ref.file_id).read()
    return out


def request(*, model: str, content: list[dict], max_tokens: int, system: str | None = None, effort: str | None = None,
            code_execution: bool = False, skills: list[dict] | None = None) -> dict:
    """A Messages request. `content` is the user turn's blocks; uploaded files go in as
    `{"type": "container_upload", "file_id": ...}`. Skills run in the code-execution container."""
    req = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}],
           "extra_body": {}, **({"system": system} if system else {})}
    if effort:
        req["extra_body"]["output_config"] = {"effort": effort}
    if code_execution or skills:
        req["extra_body"]["tools"] = [CODE_EXECUTION]
        req["betas"] = [FILES_BETA] + ([SKILLS_BETA] if skills else [])
    if skills:
        req["extra_body"]["container"] = {"skills": skills}
    return req


def file_block(file_id: str) -> dict:
    return {"type": "container_upload", "file_id": file_id}


def _once(api, req: dict, deadline: float, label: str):
    retries = 0
    messages = api.beta.messages if "betas" in req else api.messages
    while True:
        if time.time() >= deadline:
            raise DeadlineExceeded(f"deadline reached before attempt {retries + 1}")
        try:
            with messages.stream(**req) as s:
                return s.get_final_message(), retries
        except TRANSIENT as e:
            retries += 1
            print(f"    {label} attempt {retries} failed: {type(e).__name__}: {e}", flush=True)
            if retries >= TRIES:
                raise
            pause = min(60, 2 ** retries) * (0.5 + random.random())
            if time.time() + pause >= deadline:
                raise DeadlineExceeded(f"deadline reached after {retries} failed attempts; last: {type(e).__name__}: {e}")
            time.sleep(pause)


def stream(req: dict, deadline: float, api=None, label: str = ""):
    """Run `req` to the end of the model's turn. Returns (message, usage, retries): the last message,
    with `content` holding every block of the turn across pause_turn continuations."""
    api = api or connect()
    req = dict(req, messages=list(req["messages"]), extra_body=dict(req.get("extra_body") or {}))
    usage, retries, blocks = dict.fromkeys(USAGE_KEYS, 0), 0, []
    for _ in range(MAX_CONTINUATIONS + 1):
        msg, r = _once(api, req, deadline, label)
        retries += r
        if not msg.model.startswith(req["model"]):
            raise ServedModelMismatch(f"served model {msg.model} != requested {req['model']}")
        for k in USAGE_KEYS:
            usage[k] += getattr(msg.usage, k, 0) or 0
        blocks += msg.content
        if msg.stop_reason != "pause_turn":
            msg.content = blocks
            return msg, usage, retries
        req["messages"].append({"role": "assistant", "content": msg.content})
        c = req["extra_body"].get("container")
        req["extra_body"]["container"] = dict(c, id=msg.container.id) if isinstance(c, dict) else msg.container.id
    raise RuntimeError("pause_turn continuation cap reached")
