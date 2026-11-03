"""Loaders for the txn_panel source: the raw panel, its annotations, and who is in it.

Every family built on this source reads through here, so a fact about the data is written once
(annotations/) and a split is applied the same way everywhere (by company, see entities.yaml).
"""

from __future__ import annotations

import csv
import gzip
import pathlib

import yaml

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "raw" / "sensor_panel.csv.gz"
BRIEF = HERE / "assignment" / "brief.txt"
GRADER_ONLY = HERE / "grader_only"
ANNOTATIONS = HERE / "annotations"
PANEL_END = "2018-12-31"   # last date in the raw panel


def _yaml(name: str):
    return yaml.safe_load((ANNOTATIONS / name).read_text())


def companies() -> dict[str, dict]:
    return _yaml("entities.yaml")["companies"]


def sensors_of(names) -> list[str]:
    """Sensor tickers of the given companies, sorted."""
    c = companies()
    return sorted(t for n in names for t in c[n]["sensors"])


def company_of_sensor(ticker: str) -> str:
    return next(n for n, c in companies().items() if ticker in c["sensors"])


def company_of_series(series_id: str) -> str:
    return next(n for n, c in companies().items() if series_id in c["series"])


def data_artifacts() -> tuple[list[dict], list[dict]]:
    """(required, optional) natural artifacts in original coordinates."""
    a = _yaml("data_artifacts.yaml")
    return a["required"], a["optional"]


def company_facts() -> tuple[dict[str, list[tuple[str, str | None]]], dict[str, str]]:
    """({series: [(text, public_from)]}, {series: low-signal reason})."""
    y = _yaml("company_facts.yaml")
    facts = {s: [(f["text"], f["public_from"]) for f in fs] for s, fs in y["facts"].items()}
    return facts, y["low_signal"]


def read_rows(path: pathlib.Path = RAW) -> list[dict]:
    """The panel as csv rows of strings, exactly as stored (for builders that re-emit csv)."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as fh:
        return list(csv.DictReader(fh))


def load_df(sensors=None):
    """The panel as a DataFrame (date parsed), optionally restricted to some sensor tickers."""
    import pandas as pd
    df = pd.read_csv(RAW, parse_dates=["date"])[["date", "ct", "amt", "ticker", "industry", "source_id"]]
    return df if sensors is None else df[df.ticker.isin(list(sensors))].reset_index(drop=True)
