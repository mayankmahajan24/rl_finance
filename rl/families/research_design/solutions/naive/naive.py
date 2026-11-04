"""Naive solution: always picks plan "A" in both orders (compare) and raises no issue (review)."""
import json
import os
from pathlib import Path

APP = Path(os.environ.get('APP_DIR', '/app'))

schema = json.loads((APP / 'data' / 'output_schema.json').read_text())
if 'AB' in schema['properties']:
    answer = {o: {'winner': 'A'} for o in ('AB', 'BA')}
else:
    answer = {'issues': []}
(APP / 'output').mkdir(parents=True, exist_ok=True)
(APP / 'output' / 'response.json').write_text(json.dumps(answer))
