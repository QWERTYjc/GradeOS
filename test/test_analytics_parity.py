import copy
import json
from pathlib import Path
import unittest

from gradeos_analysis import analyze


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in {'generated_at', 'methods'}}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


class AnalyticsParityTests(unittest.TestCase):
    def test_extracted_functions_match_original_gradeos_on_neutral_records(self):
        path = Path(__file__).parent / 'fixtures/analytics-parity.json'
        for case in json.loads(path.read_text()):
            with self.subTest(records=len(case['input']['records'])):
                original = copy.deepcopy(case['input'])
                self.assertEqual(json.loads(json.dumps(stable(analyze(case['input'])))), case['expected'])
                self.assertEqual(case['input'], original, 'reporting must not mutate scores')
