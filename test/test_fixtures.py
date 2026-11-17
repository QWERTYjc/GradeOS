import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter, PdfReader

from evals.fixture_inputs import ROOT, fixture_directory, input_documents, prepare, sha
from evals.fixture_evaluation import evaluate, reference


class FixtureTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / 'm2/input.json').exists(), 'Private M2 evaluation materials are not bundled')
    def test_official_m2_items_are_read_from_preserved_pdf(self):
        fixture = fixture_directory('m2')
        ref = reference(fixture)
        self.assertEqual(len(ref['items']), 34)
        self.assertEqual(sum(row['score'] for row in ref['items']), 76)
        self.assertEqual(sum(row['max_score'] for row in ref['items']), 100)
        self.assertEqual(len({row['question_id'] for row in ref['items']}), 12)
        self.assertEqual(next(row['score'] for row in ref['items'] if row['item_id'] == '10(c)(i)'), 2)

    def test_nonterminal_and_tampered_results_never_open_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            with patch('evals.fixture_evaluation.reference', side_effect=AssertionError('labels read')):
                for summary in [{'status': 'running'}, {'status': 'submitted', 'active_agents_at_summary': 1}]:
                    (run / 'summary.json').write_text(json.dumps(summary))
                    with self.assertRaises(ValueError):
                        evaluate(run, Path('missing-reference'))
                (run / 'summary.json').write_text('{"status":"submitted"}')
                (run / 'grading.json').write_text('{}')
                (run / 'grading.sha256').write_text('tampered')
                with self.assertRaises(ValueError):
                    evaluate(run, Path('missing-reference'))
                (run / 'summary.json').write_text('{"status":"incomplete"}')
                self.assertEqual(evaluate(run, Path('missing-reference'))['labels_loaded'], False)

    @unittest.skipUnless((ROOT / 'm2/input.json').exists(), 'Private M2 evaluation materials are not bundled')
    def test_posthoc_compensating_errors_fail_even_when_total_matches(self):
        fixture = fixture_directory('m2')
        rows = reference(fixture)['items']
        grade = {'items': [{k: v for k, v in row.items() if k != 'question_id'} for row in rows],
                 'total_score': 76, 'max_score': 100}
        lower = next(row for row in grade['items'] if row['score'] > 0)
        higher = next(row for row in grade['items'] if row['score'] < row['max_score'] and row is not lower)
        lower['score'] -= 1
        higher['score'] += 1
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / 'summary.json').write_text('{"status":"submitted"}')
            (run / 'grading.json').write_text(json.dumps(grade))
            (run / 'grading.sha256').write_text(sha(run / 'grading.json'))
            result = evaluate(run, fixture)
            self.assertEqual(result['verdict'], 'M2 fixture regression fail')
            self.assertEqual(result['students']['student-001']['matched_items'], 32)
            self.assertEqual(len(result['students']['student-001']['questions']), 12)

    def test_preparation_uses_declared_pages_and_excludes_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / 'fixture'
            fixture.mkdir()
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=300)
            writer.add_blank_page(width=300, height=400)
            with (fixture / 'source.pdf').open('wb') as handle:
                writer.write(handle)
            document = {'path': 'source.pdf', 'sha256': sha(fixture / 'source.pdf'), 'page_count': 2, 'pages': [2]}
            manifest = {'version': 1, 'documents': {'scheme': document, 'student': document}}
            (fixture / 'input.json').write_text(json.dumps(manifest))
            (fixture / 'posthoc').mkdir()
            (fixture / 'posthoc/labels.json').write_text('DO_NOT_COPY_REFERENCE_SENTINEL')
            output = Path(temp) / 'prepared'
            result = prepare(fixture, output)
            self.assertFalse(result['labels_loaded'])
            pdf = PdfReader(output / 'student/original.pdf')
            self.assertEqual(len(pdf.pages), 1)
            self.assertEqual(float(pdf.pages[0].mediabox.width), 300)
            prepared = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(set(prepared['documents']), {'scheme', 'student'})
            for path in output.rglob('*.json'):
                self.assertNotIn('DO_NOT_COPY_REFERENCE_SENTINEL', path.read_text())
            manifest['documents']['reference'] = document
            (fixture / 'input.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                input_documents(fixture)
            manifest['documents'].pop('reference')
            manifest['documents']['student'] = {**document, 'path': '../source.pdf'}
            (fixture / 'input.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                input_documents(fixture)

    def test_cohort_terminal_roster_required_before_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / 'summary.json').write_text(json.dumps({'status': 'partial_completed', 'students': [
                {'student_id': 'one', 'status': 'failed'}], 'active_agents_at_summary': 0}))
            (run / 'plan.json').write_text('{"students":{"one":{},"two":{}}}')
            with patch('evals.fixture_evaluation.reference', side_effect=AssertionError('labels read')):
                with self.assertRaises(ValueError):
                    evaluate(run, Path('missing-reference'))


if __name__ == '__main__':
    unittest.main()
