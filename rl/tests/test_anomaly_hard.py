"""anomaly_hard prototype grader (rl/experiments/anomaly_hard/grade.py), graded offline on one train task built into a
scratch folder (the built tasks under rl/tasks/proto are left alone).

  - A known pass (the answer key) scores 1.0 on each of the task's three hidden panels, and so does a paraphrase of it (other confidence values on the same side
    of 0.5, cleaned values moved within a fraction of the source's own noise).
  - A known fail (do nothing) and the negation of the answer key (its confidence inverted) score 0.
  - Lopsided and constant answers (distrust everything with a perfect cleaned series) score 0.
  - The gates: a look-ahead scorer fails point in time; a missing write-up scores 0.
  - Agent code cannot read the answer key on disk (only where the grader can isolate it: root with namespaces).
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

RL = pathlib.Path(__file__).resolve().parents[1]
HERE = RL / "experiments" / "anomaly_hard"
SOL = HERE / "solutions"
sys.path[:0] = [str(HERE)]

pytestmark = pytest.mark.slow

ORACLE_WRAP = """import pathlib, runpy, sys
import numpy as np, pandas as pd
a = sys.argv
runpy.run_path({oracle!r}, run_name='__main__')
out = a[a.index('--output') + 1]
o = pd.read_csv(out)
{edit}
o.to_csv(out, index=False)
"""


def _experiment_module(name: str):
    """The experiment's own module by file path (rl/build.py shares the name `build`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"anomaly_hard_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def task(tmp_path_factory):
    build = _experiment_module("build")
    from families._shared import build_panel
    d = tmp_path_factory.mktemp("anomaly_hard") / "anomhard-train-test"
    build.build_task(build_panel.context("txn_panel", "train"), d, 320001, False)
    return d


def grade_sol(task, sol: pathlib.Path, monkeypatch, trusted=False, writeup=True, tmp=None):
    import grade
    if trusted:
        monkeypatch.setattr(grade, "TRUSTED", grade.TRUSTED | {(sol / "score.py").resolve()})
    monkeypatch.setenv("ORACLE_TASK", str(task))
    truth = json.loads((task / "tests" / "gold.json").read_text())
    data = pd.read_csv(task / "tests" / "eval_panel.csv.gz", parse_dates=["date"])
    clean = pd.read_csv(task / "tests" / "truth_panel.csv.gz", parse_dates=["date"])
    w = (tmp or sol) / "writeup.md"
    if writeup:
        w.write_text("method note")
    reward, d = grade.score(truth, data, clean, sol, w if writeup else w.with_name("missing.md"))
    return reward, d


def variant(tmp_path, name, edit):
    d = tmp_path / name
    d.mkdir()
    (d / "score.py").write_text(ORACLE_WRAP.format(oracle=str(SOL / "oracle" / "score.py"), edit=edit))
    return d


def test_answer_key_passes(task, monkeypatch):
    reward, d = grade_sol(task, SOL / "oracle", monkeypatch, trusted=True, tmp=task)
    assert reward == pytest.approx(1.0, abs=1e-3), d["gates"]


def test_answer_key_passes_on_every_hidden_panel(task, monkeypatch, tmp_path):
    import grade
    monkeypatch.setenv("ORACLE_TASK", str(task))
    monkeypatch.setenv("WRITEUP_JUDGE", "skip")       # the data reward only (the write-up has its own tests)
    w = tmp_path / "writeup.md"
    w.write_text("method note")
    reward, d = grade.grade_task(task, SOL / "oracle", w)
    assert len(d["panels"]) == 3 and reward == pytest.approx(1.0, abs=1e-3), d["panels"]


# a per-row number in [0, 1) fixed by the row's keys alone (so it is point in time)
ROW_U = "u = pd.util.hash_pandas_object(o[['date', 'ticker', 'source_id']], index=False).to_numpy() % 1000 / 1000\n"


def test_paraphrased_answer_key_passes(task, monkeypatch, tmp_path):
    # the same verdicts and repairs in another form: confidence moved off 0 / 1 and varying row by row (0.95-0.99 on
    # trusted rows, 0.01-0.05 on distrusted ones), cleaned counts and dollars moved 0.5%
    sol = variant(tmp_path, "para", ROW_U + "o['confidence'] = np.where(o.confidence < 0.5, 0.01, 0.95) + 0.04 * u\n"
                                            "o['clean_ct'] = o.clean_ct * 1.005\no['clean_amt'] = o.clean_amt * 1.005")
    reward, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert reward > 0.97, (d["gates"], d["confidence_score"], d["clean_score"], d["stability"])


def test_answer_key_on_a_few_fixed_levels_fails_continuity(task, monkeypatch, tmp_path):
    # right verdicts, but confidence on two fixed levels (0.3 / 0.9): not a probability on a continuous scale
    sol = variant(tmp_path, "levels", "o['confidence'] = np.where(o.confidence < 0.5, 0.3, 0.9)")
    reward, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert reward == 0.0 and d["gates"]["continuous"] is False


def test_negated_answer_key_fails(task, monkeypatch, tmp_path):
    sol = variant(tmp_path, "neg", "o['confidence'] = 1.0 - o.confidence")
    reward, _ = grade_sol(task, sol, monkeypatch, trusted=True)
    assert reward == 0.0


def test_do_nothing_fails(task, monkeypatch, tmp_path):
    reward, _ = grade_sol(task, SOL / "naive", monkeypatch, tmp=tmp_path)
    assert reward == 0.0


def test_distrust_everything_with_perfect_cleaning_fails(task, monkeypatch, tmp_path):
    # the answer key's cleaned series with every row at confidence 0: one fixed level, zeroed by the continuity gate
    reward, d = grade_sol(task, SOL / "distrust_all", monkeypatch, tmp=tmp_path)
    assert reward == 0.0 and d["gates"]["continuous"] is False


def test_distrust_everything_earns_no_confidence_credit(task, monkeypatch, tmp_path):
    # the same, with confidence varying row by row under 0.5 so it passes the continuity gate: the confidence part
    # scores nothing, and the total is at most the cleaned series' and stability's share (55%)
    sol = variant(tmp_path, "distrust", ROW_U + "o['confidence'] = 0.02 + 0.4 * u")
    reward, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert d["gates"]["continuous"] is True and d["confidence_score"] == 0.0, d["gates"]
    assert reward <= 0.55 + 1e-9


def test_missing_writeup_scores_zero(task, monkeypatch):
    reward, d = grade_sol(task, SOL / "oracle", monkeypatch, trusted=True, writeup=False)
    assert reward == 0.0 and d["gates"]["writeup"] is False


def test_lookahead_fails_point_in_time(task, monkeypatch, tmp_path):
    sol = variant(tmp_path, "ahead", "o['confidence'] = 0.5 + 0.5 * (o.groupby(['ticker', 'source_id']).clean_ct"
                                     ".transform(lambda x: x.fillna(0).rank(pct=True)))")
    reward, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert reward == 0.0 and d["gates"]["point_in_time"] is False


def test_agent_code_cannot_read_the_answer_key(task, monkeypatch, tmp_path):
    import grade
    if not grade.ISOLATE:
        pytest.skip("the grader isolates agent code only as root with namespaces (the Harbor verifier does it there)")
    reward, _ = grade_sol(task, SOL / "exploit_gold_read", monkeypatch, tmp=tmp_path)
    assert reward == 0.0


# ---------------------------------------------------------------- the problems added by feedback #103
# column swaps, one measure stuck, and a step on one source across its companies. Each test edits the answer key on
# the rows of one of them. `i` is the input the script was given (row for row with its output `o`), `ev` the events.
ON_EVENTS = """import json, os
i = pd.read_csv(a[a.index('--input') + 1])
ev = json.loads((pathlib.Path(os.environ['ORACLE_TASK']) / 'tests' / 'gold.json').read_text())['events']
def rows(pick):
    m = np.zeros(len(o), bool)
    for e in ev:
        if pick(e):
            m |= ((o.ticker == e['ticker']) & (o.source_id == e['source_id'])
                  & (o.date >= e.get('shift_start', e['start'])) & (o.date <= e['end'])).to_numpy()
    return m
def as_reported(m):
    o.loc[m, 'clean_ct'] = i.ct.to_numpy()[m]
    o.loc[m, 'clean_amt'] = i.amt.to_numpy()[m]
"""
SWAP = "lambda e: e['type'] == 'column_swap'"
STUCK_ONE = "lambda e: e['type'] == 'stuck' and e.get('measure') in ('count', 'dollars')"
SOURCE_WIDE = "lambda e: bool(e.get('source_wide'))"


def _events(task, pick):
    return [e for e in json.loads((task / "tests" / "gold.json").read_text())["events"] if pick(e)]


def _gains(d, events):
    """The cleaned-series gain the grader gave each of `events` (those it scored)."""
    key = {(e["type"], e["ticker"], e["source_id"], e["start"]) for e in events}
    return [g["gain"] for g in d["clean"]["events"] if (g["type"], g["ticker"], g["source_id"], g["start"]) in key]


def _kind(d, part, kind):
    return next(r for r in d[part]["by_kind"] if r["kind"] == kind)


def test_new_problems_are_planted(task):
    swaps = _events(task, eval(SWAP))
    assert sorted(e["whole"] for e in swaps) == [False, True]
    assert len({e["ticker"] for e in swaps}) == 2                      # on two different companies
    assert sorted(e["measure"] for e in _events(task, eval(STUCK_ONE))) == ["count", "dollars"]
    wide = _events(task, eval(SOURCE_WIDE))
    assert len(wide) >= 2 and len({e["ticker"] for e in wide}) == len(wide)
    assert len({(e["source_id"], e["start"], e["end"], e["ct_mult"]) for e in wide}) == 1   # one source, same days


def test_answer_key_is_scored_on_the_new_problems(task, monkeypatch):
    _, d = grade_sol(task, SOL / "oracle", monkeypatch, trusted=True, tmp=task)
    for pick in (SWAP, STUCK_ONE, SOURCE_WIDE):
        g = _gains(d, _events(task, eval(pick)))
        assert g and all(x == pytest.approx(1.0, abs=1e-3) for x in g), (pick, g)
    assert _kind(d, "clean", "column_swap")["events"] == 2


def test_swapped_columns_left_as_reported_fail(task, monkeypatch, tmp_path):
    # the answer key everywhere else, the swapped series as reported and still trusted
    sol = variant(tmp_path, "swap_raw", ON_EVENTS + f"as_reported(rows({SWAP}))")
    reward, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert _kind(d, "clean", "column_swap")["gain"] == 0.0
    c = _kind(d, "confidence", "column_swap")
    assert c["wrong_rows"] == c["rows"] and c["brier"] > 0.9          # every row wrong, and trusted
    assert reward < 0.85, (d["confidence_score"], d["clean_score"])


def test_swap_with_only_the_count_put_right_fails(task, monkeypatch, tmp_path):
    # a near miss: the true count, but the dollar column still carrying the count
    sol = variant(tmp_path, "swap_half", ON_EVENTS + f"m = rows({SWAP})\no.loc[m, 'clean_amt'] = i.amt.to_numpy()[m]")
    _, d = grade_sol(task, sol, monkeypatch, trusted=True)
    assert _kind(d, "clean", "column_swap")["gain"] < 0.6
    c = _kind(d, "confidence", "column_swap")
    assert c["wrong_rows"] == c["rows"]                               # the ticket is still wrong on every row


def test_one_measure_stuck_left_as_reported_fails(task, monkeypatch, tmp_path):
    sol = variant(tmp_path, "stuck_raw", ON_EVENTS + f"as_reported(rows({STUCK_ONE}))")
    _, d = grade_sol(task, sol, monkeypatch, trusted=True)
    g = _gains(d, _events(task, eval(STUCK_ONE)))
    assert g and all(x == 0.0 for x in g), g
    assert _kind(d, "clean", "stuck")["gain"] < 1.0


def test_source_wide_step_left_as_reported_fails(task, monkeypatch, tmp_path):
    sol = variant(tmp_path, "wide_raw", ON_EVENTS + f"as_reported(rows({SOURCE_WIDE}))")
    _, d = grade_sol(task, sol, monkeypatch, trusted=True)
    wide = _events(task, eval(SOURCE_WIDE))
    g = _gains(d, wide)
    assert len(g) == len(wide) and all(x == 0.0 for x in g), g


def test_counts_are_written_whole_beside_a_swapped_series(task):
    import grade
    data = pd.read_csv(task / "tests" / "eval_panel.csv.gz", parse_dates=["date"])
    assert data.ct.dtype.kind == "f"                                   # the swapped rows carry dollars and cents
    text = grade.panel_csv(data)
    back = pd.read_csv(pd.io.common.StringIO(text), dtype=str)
    swapped = pd.Series(False, index=data.index)
    for e in _events(task, eval(SWAP)):
        swapped |= (data.ticker == e["ticker"]) & (data.source_id == e["source_id"]) & (data.date >= e["start"])
    assert not back.ct[~swapped.to_numpy()].str.contains(r"\.", regex=True).any()   # 36, not 36.0
    assert back.ct[swapped.to_numpy()].str.contains(r"\.", regex=True).mean() > 0.9
    assert (pd.to_numeric(back.ct) == data.ct).all()
    whole = pd.DataFrame(dict(date=pd.to_datetime(["2020-01-01"]), ct=[36], amt=[1.5]))
    assert grade.panel_csv(whole).splitlines()[1] == "2020-01-01,36,1.5"


# ---------------------------------------------------------------- early days (feedback #105): confidence only
# The first five days of every lasting problem are one more kind in the confidence part, day one weighing most.
# `late(n)`: the answer key, but for the first n days of each lasting problem the row is left as reported.
LASTING = "lambda e: e['type'] not in ('volume_spike', 'dropout', 'count_flood', 'dollar_spike', 'rollup') and not e.get('unscored')"
LATE = ON_EVENTS + """def first_days(n):
    m = np.zeros(len(o), bool)
    for e in ev:
        if ({lasting})(e):
            first = e.get('visible') or e.get('shift_start', e['start'])
            last = min(str(pd.Timestamp(first) + pd.Timedelta(days=n - 1))[:10], e['end'])
            m |= ((o.ticker == e['ticker']) & (o.source_id == e['source_id']) & (o.date >= first) & (o.date <= last)).to_numpy()
    return m
m = first_days({n})
as_reported(m)
{conf}
""".replace("{lasting}", LASTING)


def _late(tmp_path, name, n, conf=""):
    return variant(tmp_path, name, LATE.replace("{n}", str(n)).replace("{conf}", conf))


def test_answer_key_has_an_early_days_kind(task, monkeypatch):
    reward, d = grade_sol(task, SOL / "oracle", monkeypatch, trusted=True, tmp=task)
    k = _kind(d, "confidence", "early_days")
    assert reward == pytest.approx(1.0, abs=1e-3) and k["rows"] > 20 and k["wrong_rows"] == 0 and k["brier"] < 0.001


def test_catching_a_problem_late_costs_most_on_day_one(task, monkeypatch, tmp_path):
    # still trusted while unrepaired: one day late, then three days late
    key = grade_sol(task, SOL / "oracle", monkeypatch, trusted=True, tmp=task)[1]["confidence_score"]
    d1 = grade_sol(task, _late(tmp_path, "late1", 1), monkeypatch, trusted=True)[1]
    d3 = grade_sol(task, _late(tmp_path, "late3", 3), monkeypatch, trusted=True)[1]
    b1, b3 = _kind(d1, "confidence", "early_days")["brier"], _kind(d3, "confidence", "early_days")["brier"]
    assert key > d1["confidence_score"] > d3["confidence_score"]
    assert b3 > b1 > 0.2                       # the kind's own error: most of it is already lost on day one
    assert b1 > 0.5 * b3                       # 16 of the 31 parts of weight sit on day one, 28 on days one to three


def test_doubting_the_unrepaired_early_days_beats_trusting_them(task, monkeypatch, tmp_path):
    # three days late either way; the second answer says so (confidence 0.05-0.09 on those rows)
    trusted = grade_sol(task, _late(tmp_path, "late3", 3), monkeypatch, trusted=True)[1]
    doubted = grade_sol(task, _late(tmp_path, "late3d", 3, ROW_U + "o.loc[m, 'confidence'] = 0.05 + 0.04 * u[m]"),
                        monkeypatch, trusted=True)[1]
    assert _kind(doubted, "confidence", "early_days")["brier"] < 0.5 * _kind(trusted, "confidence", "early_days")["brier"]
    assert doubted["confidence_score"] > trusted["confidence_score"]


def test_doubting_everything_early_is_not_free(task, monkeypatch, tmp_path):
    # trigger-happy: the answer key's repairs, but every early row distrusted although its cleaned value is right
    sol = variant(tmp_path, "jumpy", LATE.replace("{n}", "5").replace("\nas_reported(m)\n", "\n").replace(
        "{conf}", ROW_U + "o.loc[m, 'confidence'] = 0.05 + 0.04 * u[m]"))
    d = grade_sol(task, sol, monkeypatch, trusted=True)[1]
    assert _kind(d, "confidence", "early_days")["brier"] > 0.7
    assert d["confidence_score"] < 0.9
