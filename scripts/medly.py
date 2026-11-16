import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.medly_assets import prepare_answer

parser = argparse.ArgumentParser(description='Prepare an existing Medly source sample; no grading requests or labels.')
parser.add_argument('--answer', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
print(json.dumps(prepare_answer(args.answer, args.output), indent=2))
