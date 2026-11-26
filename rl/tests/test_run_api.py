"""The API runner (rl/harness/run_api.py) and its client (rl/harness/client.py), against a fake API: no
model calls. One task per family goes end to end: request, the model's <file> blocks written into a
local task layout, the task's own verifier, a run record; a re-run resumes instead of repeating."""

from __future__ import annotations

import contextlib
import json
import time
from types import SimpleNamespace

import pytest

import client
import records
import run_api
from conftest import built


USAGE = SimpleNamespace(input_tokens=1000, output_tokens=100, cache_read_input_tokens=50, cache_creation_input_tokens=10)


def message(text="", stop="end_turn", model="claude-opus-5-5-20261001", container=None):
    return SimpleNamespace(model=model, stop_reason=stop, usage=USAGE, container=container,
                           content=[SimpleNamespace(type="text", text=text)])


class FakeAPI:
    """Serves `answer(request)` (a message, or an exception to raise) for each call, on both the
    beta and plain Messages endpoints; records requests and file uploads."""

    def __init__(self, answer):
        self.answer, self.calls, self.uploads, self.deleted = answer, [], [], []
        self.messages = self.beta = self.files = self
        self.beta.files = self

    @contextlib.contextmanager
    def stream(self, **req):
        self.calls.append(json.loads(json.dumps(req, default=str)))
        out = self.answer(req)
        if isinstance(out, Exception):
            raise out
        yield SimpleNamespace(get_final_message=lambda: out)

    def upload(self, file):
        self.uploads.append(file[0])
        return SimpleNamespace(id=f"file_{len(self.uploads)}")

    def delete(self, file_id):
        self.deleted.append(file_id)


# ---- client -----------------------------------------------------------------------------------

def test_stream_follows_pause_turn_and_sums_usage():
    msgs = iter([message("part one", stop="pause_turn", container=SimpleNamespace(id="c1")), message("part two")])
    api = FakeAPI(lambda req: next(msgs))
    req = client.request(model="claude-opus-5-5", system="s", content=[{"type": "text", "text": "u"}],
                         max_tokens=10, code_execution=True)
    msg, usage, retries = client.stream(req, time.time() + 60, api)
    assert [b.text for b in msg.content] == ["part one", "part two"] and retries == 0
    assert usage == {"input_tokens": 2000, "output_tokens": 200, "cache_read_input_tokens": 100,
                     "cache_creation_input_tokens": 20}
    assert api.calls[1]["extra_body"]["container"] == "c1" and len(api.calls[1]["messages"]) == 2
    assert req["messages"] == [req["messages"][0]]                     # the caller's request is untouched
    assert req["extra_body"]["tools"] == [client.CODE_EXECUTION]


def test_served_model_must_match():
    with pytest.raises(client.ServedModelMismatch):
        client.stream(client.request(model="claude-opus-5-5", system="s", content=[], max_tokens=10),
                      time.time() + 60, FakeAPI(lambda req: message(model="claude-sonnet-5-5")))


def test_backoff_never_passes_the_deadline(monkeypatch):
    err = client.anthropic.APIConnectionError(request=client.httpx.Request("POST", "https://x"))
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    with pytest.raises(client.DeadlineExceeded):
        client.stream(client.request(model="m", system="s", content=[], max_tokens=10), time.time() + 1,
                      FakeAPI(lambda req: err))


# ---- runner -----------------------------------------------------------------------------------

def answer_for(task) -> str:
    """A well-formed answer in the task's output format, as <file> blocks."""
    meta = records.identity(task)
    fam, d = meta["family"], task
    if fam == "data_audit":
        files = {"output/issues.json": "[]"}
    elif fam == "anomaly_scoring":
        files = {"solution/score.py": ("import argparse\nimport pandas as pd\nap = argparse.ArgumentParser()\n"
                                       "ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()\n"
                                       "df = pd.read_csv(a.input); df['anomaly_score'] = 0.0\n"
                                       "df[['date', 'ticker', 'source_id', 'anomaly_score']].to_csv(a.output, index=False)\n")}
    elif fam == "growth_thesis":
        files = {"output/answer.json": json.dumps({"fastest": "X", "growth": {}, "unreliable": []}),
                 "output/memo.md": "X grew fastest."}
    elif fam == "kpi_nowcast":
        g = json.loads((d / "tests" / "gold.json").read_text())
        fc = {"target_period": g["target_period"].replace(" ", ""), "unit": g["unit"], "point": g["actual"],
              "low": g["actual"] * 0.98, "high": g["actual"] * 1.02, "interval_level": 0.95, "in_sample": [],
              "vs_consensus": "no_consensus",
              "metric_history": [{"period_end": e, "value": v[-1]} for e, v in g["metric_history"].items()]}
        files = {"output/answer.md": f"Estimate.\n\n```json\n{json.dumps(fc)}\n```"}
    else:
        files = {"output/response.json": json.dumps({"winner": "A", "confidence": 3, "goal_type": "single_name_kpi",
                                                     "error_asymmetry": "symmetric", "decisive_tenets": [],
                                                     "key_differentiator": "x", "rationale": "x"})}
    return "Done.\n" + "".join(f'<file path="/app/{p}">\n{body}\n</file>\n' for p, body in files.items())


CASES = [("bench", "audit-bench-001"), ("bench", "anomaly-bench-001"), ("bench", "thesis-bench-001"),
         ("bench", "kn-produce-DAL-2017Q4"), ("eval", "rd-funding-S1")]


@pytest.mark.slow
@pytest.mark.parametrize("split, task_id", CASES)
def test_every_family_end_to_end(split, task_id, tmp_path, monkeypatch, offline):
    task = built(split, task_id)
    api = FakeAPI(lambda req: message(answer_for(task)))
    monkeypatch.setattr(run_api, "RL", tmp_path / "rl")
    monkeypatch.setattr(run_api.client, "connect", lambda: api)
    monkeypatch.setattr(run_api.instrument, "require_approved", lambda f: None)
    tools = "code_execution" in run_api.family(records.identity(task)["family"]).get("tools", [])
    argv = ["--split", split, "--tasks", task_id, "--model", "claude-opus-5-5", "--budget", "1", "--run-id", "t"]
    run_api.main(argv)
    out = tmp_path / "rl" / "runs" / "api" / split / "t"
    [r] = records.load([out / "records.jsonl"])
    assert records.validate(r) == []
    assert (r["task_id"], r["status"], r["served_model"]) == (task_id, "ok", "claude-opus-5-5-20261001")
    assert r["rewards"] and r["content_sha256"] == records.identity(task)["content_sha256"]
    assert r["cost_usd"] > 0 and r["runner"] == {"name": "rl/harness/run_api.py", "run_id": "t"}
    assert bool(api.uploads) == tools and sorted(api.deleted) == sorted(f"file_{i + 1}" for i in range(len(api.uploads)))
    run_api.main(argv)                                              # resumes: nothing left to run
    assert len(api.calls) == 1 and len(records.load([out / "records.jsonl"])) == 1
    with pytest.raises(SystemExit):
        run_api.main(argv[:-2] + ["--run-id", "t", "--k", "2"])    # same run, other arguments


def test_failures_keep_their_class(tmp_path, monkeypatch, offline):
    task = built("bench", "audit-bench-001")
    monkeypatch.setattr(run_api, "RL", tmp_path / "rl")
    monkeypatch.setattr(run_api.instrument, "require_approved", lambda f: None)
    cases = {"refusal": message("no", stop="refusal"), "truncated": message("<file path", stop="max_tokens"),
             "parse_error": message("no file blocks here"), "error": message("x", model="other-model")}
    for want, msg in cases.items():
        monkeypatch.setattr(run_api.client, "connect", lambda: FakeAPI(lambda req: msg))
        run_api.main(["--split", "bench", "--tasks", task.name, "--model", "claude-opus-5-5", "--budget", "1",
                      "--run-id", want])
        [r] = records.load([tmp_path / "rl" / "runs" / "api" / "bench" / want / "records.jsonl"])
        assert r["status"] == want, r
        assert records.score(r) == (None if want == "error" else 0.0)


def test_heldout_needs_opt_in_and_live_runs_need_a_budget():
    with pytest.raises(SystemExit):
        run_api.main(["--split", "heldout", "--model", "m", "--dry-run"])
    with pytest.raises(SystemExit):
        run_api.main(["--split", "bench", "--model", "m"])


def test_answer_files_stay_under_app():
    text = '<file path="/app/output/a.md">\nhi\n</file><file path="/app/output/../../etc/x">\nno\n</file>'
    assert run_api.answer_files(text) == {"output/a.md": "hi"}


def test_generated_pngs_keeps_only_sandbox_pngs():
    names = {"a": "/tmp/fig1.png", "b": "results.csv"}
    files = SimpleNamespace(retrieve_metadata=lambda i: SimpleNamespace(filename=names[i]),
                            download=lambda i: SimpleNamespace(read=lambda: i.encode()))
    refs = [SimpleNamespace(type="bash_code_execution_output", file_id=i) for i in names]
    content = [SimpleNamespace(type="text"),
               SimpleNamespace(type="bash_code_execution_tool_result",
                               content=SimpleNamespace(type="bash_code_execution_result", content=refs))]
    assert client.generated_pngs(SimpleNamespace(beta=SimpleNamespace(files=files)), content) == {"fig1.png": b"a"}
