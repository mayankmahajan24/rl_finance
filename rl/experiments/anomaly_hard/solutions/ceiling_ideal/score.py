"""Grader check: the ceiling (solutions/ceiling) with exact imputation (no estimation noise)."""
import pathlib
import runpy

runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / 'ceiling' / 'score.py'),
               init_globals={'NOISE_OVERRIDE': 0.0}, run_name='__main__')
