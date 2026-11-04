"""The one model judge every model-graded verifier uses. Copied into a judged task's tests/ beside
common.py, with tests/judge.json: the family's pinned judge (model, effort, votes, max_tokens, from
`judge` in family.yaml, part of its instrument).

  - one client, structured output, timeouts, retries with backoff on rate limits, overload and
    connection errors; no model fallback (a different judge would be a different instrument)
  - every call returns what it was graded with: requested and served model, the judge prompt's
    fingerprint, votes, and whether the answer came from the cache
  - n-vote judging (`votes` > 1); `majority` combines per-item verdicts
  - a cache keyed by the exact request (judge config, prompt, the answer and gold it contains, vote
    index) under $JUDGE_CACHE, so re-grading a saved run is free and returns the same judgments
  - one no-key policy: `unavailable()` says why the judge can't run, and the verifier reports the
    judged metrics as not graded. It never swaps in another grader unless asked (JUDGE=keyword)

JUDGE_MODEL, JUDGE_EFFORT and JUDGE_VOTES override the pinned config for experiments; the details
then record the override.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path

TESTS = Path(os.environ.get('TESTS_DIR', '/tests'))
RETRIES = 5
TIMEOUT_S = 600


class JudgeError(RuntimeError):
    pass


def config(path: Path | None = None) -> dict:
    """The pinned judge config, with any environment overrides applied and recorded."""
    cfg = json.loads((path or TESTS / 'judge.json').read_text())
    over = {k: os.environ[e] for k, e in (('model', 'JUDGE_MODEL'), ('effort', 'JUDGE_EFFORT'), ('votes', 'JUDGE_VOTES'))
            if os.environ.get(e) and str(cfg.get(k)) != os.environ[e]}
    if 'votes' in over:
        over['votes'] = int(over['votes'])
    return dict(cfg, **over, **({'overridden': sorted(over)} if over else {}))


def unavailable() -> str | None:
    """Why the judge can't run here, or None when it can."""
    if not os.environ.get('ANTHROPIC_API_KEY'):
        return 'not graded: no ANTHROPIC_API_KEY for the judge'
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return 'not graded: the judge client (anthropic) is not installed'
    return None


def fingerprint(system: str, schema: dict | None) -> str:
    """Hash of the judge prompt and output schema: what the judge is asked, before any answer."""
    return hashlib.sha256((system + '\0' + json.dumps(schema, sort_keys=True)).encode()).hexdigest()[:12]


def _request(cfg: dict, system: str, user: str, schema: dict | None) -> dict:
    output = {**({'effort': cfg['effort']} if cfg.get('effort') else {}),
              **({'format': {'type': 'json_schema', 'schema': schema}} if schema else {})}
    return {'model': cfg['model'], 'max_tokens': cfg.get('max_tokens', 16000), 'system': system,
            'messages': [{'role': 'user', 'content': user}], **({'output_config': output} if output else {})}


def _call(client, req: dict):
    import anthropic
    for attempt in range(RETRIES):
        try:
            with client.messages.stream(**req) as stream:
                return stream.get_final_message()
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APITimeoutError,
                anthropic.InternalServerError) as e:
            if attempt == RETRIES - 1:
                raise JudgeError(f'judge call failed after {RETRIES} tries: {type(e).__name__}: {e}') from e
            time.sleep(min(60, 2 ** attempt * 2))


def judge(system: str, user: str, schema: dict | None = None, cfg: dict | None = None, client=None) -> tuple[list, dict]:
    """Ask the judge `votes` times; returns (parsed outputs, one per vote; meta for details.json)."""
    cfg = cfg or config()
    req = _request(cfg, system, user, schema)
    cache = Path(os.environ['JUDGE_CACHE']) if os.environ.get('JUDGE_CACHE') else None
    outs, served, hits = [], [], 0
    for vote in range(int(cfg.get('votes', 1))):
        key = hashlib.sha256(json.dumps({'request': req, 'vote': vote}, sort_keys=True).encode()).hexdigest()
        hit = cache / f'{key}.json' if cache else None
        if hit and hit.exists():
            rec = json.loads(hit.read_text())
            hits += 1
        else:
            if client is None:
                import anthropic
                client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=0)
            msg = _call(client, req)
            if msg.stop_reason == 'refusal':
                raise JudgeError('judge refused')
            if msg.stop_reason == 'max_tokens':
                raise JudgeError('judge output truncated (max_tokens)')
            text = next(b.text for b in msg.content if b.type == 'text')
            rec = {'served_model': msg.model, 'text': text}
            if hit:
                hit.parent.mkdir(parents=True, exist_ok=True)
                hit.write_text(json.dumps(rec))
        served.append(rec['served_model'])
        outs.append(json.loads(rec['text']) if schema else rec['text'])
    meta = {'requested_model': cfg['model'], 'served_model': sorted(set(served)), 'effort': cfg.get('effort'),
            'votes': int(cfg.get('votes', 1)), 'prompt_fingerprint': fingerprint(system, schema),
            'cached_votes': hits, **({'overridden': cfg['overridden']} if cfg.get('overridden') else {})}
    return outs, meta


def majority(votes: list[dict], field: str) -> dict:
    """Per-item majority over n votes of {item: {field: verdict, ...}}; a tie takes the first vote's
    verdict. Each item also records the split, so flaky items show in details."""
    out = {}
    for item in votes[0]:
        seen = [v[item][field] for v in votes if item in v]
        top = Counter(seen).most_common()
        pick = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else seen[0]
        out[item] = dict(next(v[item] for v in votes if v[item][field] == pick),
                         **({'votes': dict(Counter(map(str, seen)))} if len(votes) > 1 else {}))
    return out
