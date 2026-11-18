"""Evaluator controls; no model requests or M2 values."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.evaluate import compare, remap_ids


class EvaluationTests(unittest.TestCase):
    def test_identifier_mapping_is_bijective_and_preserves_awards(self):
        grade = {'items': [{'item_id': 'Bii', 'score': 1, 'max_score': 2, 'reason': 'literal evidence'}]}
        mapped = remap_ids(grade, {'Bii': 'B(ii)'})
        self.assertEqual(mapped['items'][0]['score'], 1)
        self.assertEqual(grade['items'][0]['item_id'], 'Bii')
        self.assertEqual(mapped['items'][0]['reason'], 'literal evidence')
        with self.assertRaises(ValueError):
            remap_ids(grade, {})
        with self.assertRaises(ValueError):
            remap_ids({'items': [{'item_id': 'a'}, {'item_id': 'b'}]}, {'a': 'x', 'b': 'x'})

    def test_compensating_errors_do_not_pass(self):
        reference = {'items': [{'item_id': 'alpha', 'score': 2, 'max_score': 3},
                               {'item_id': 'beta', 'score': 1, 'max_score': 3}]}
        grade = {'items': [{'item_id': 'alpha', 'score': 3, 'max_score': 3},
                           {'item_id': 'beta', 'score': 0, 'max_score': 3}],
                 'total_score': 3, 'max_score': 6}
        report = compare(grade, reference)
        self.assertEqual(report['verdict'], 'fail')
        self.assertEqual(report['absolute_item_error'], 2)

    def test_missing_extra_and_unknown_items_remain_visible(self):
        reference = {'items': [{'item_id': 'alpha', 'score': 1, 'max_score': 3}]}
        grade = {'items': [{'item_id': 'beta', 'score': None, 'max_score': 3}],
                 'total_score': None, 'max_score': 3}
        report = compare(grade, reference)
        self.assertEqual(report['missing_items'], ['alpha'])
        self.assertEqual(report['extra_items'], ['beta'])
        self.assertIsNone(report['absolute_item_error'])


if __name__ == '__main__':
    unittest.main()
