"""Posthoc-only evaluator. Never imported by the grading runtime."""
from __future__ import annotations

import json
import re
from pathlib import Path

from evals.evaluate import compare
from evals.fixture_inputs import input_documents, sha
from evals.hkeaa_reference import _reference_result_summary


def reference(directory: Path) -> dict:
    input_documents(directory)
    contract = json.loads((directory / 'posthoc/contract.json').read_text())
    for name, expected_hash in contract['files'].items():
        path = (directory / 'posthoc' / name).resolve()
        if path.parent != (directory / 'posthoc').resolve() or sha(path) != expected_hash:
            raise ValueError('Posthoc reference hash mismatch')
    labels = json.loads((directory / 'posthoc/labels.json').read_text())
    parsed = _reference_result_summary(directory / 'posthoc' / contract['score_details'])
    if (parsed['item_count'] != contract['item_count'] or
            parsed['item_awarded_total'] != labels['expected_reference_score'] or
            parsed['subject_mark'] != labels['expected_reference_score'] or
            parsed['item_max_total'] != labels['expected_rubric_total'] or
            len(parsed['question_awarded_scores']) != labels['expected_question_count']):
        raise ValueError('Official reference integrity mismatch')
    return {'items': [{'item_id': row['item'], 'question_id': row['question'],
                       'score': row['mark'], 'max_score': row['max_mark']} for row in parsed['items']]}


def frozen_grade(directory: Path) -> dict:
    path = directory / 'grading.json'
    if sha(path) != (directory / 'grading.sha256').read_text().strip():
        raise ValueError('Frozen grading hash mismatch')
    return json.loads(path.read_text())


def terminal_grades(run: Path) -> dict:
    summary = json.loads((run / 'summary.json').read_text())
    terminal = {'submitted', 'completed', 'partial_completed', 'incomplete', 'cancelled', 'failed'}
    if summary.get('status') not in terminal or summary.get('active_agents_at_summary', 0) != 0:
        raise ValueError('Run is not terminal; posthoc labels remain unopened')
    if 'students' not in summary:
        return {'student-001': frozen_grade(run)} if summary['status'] in {'submitted', 'completed'} else {}
    plan = json.loads((run / 'plan.json').read_text())
    rows = summary['students']
    ids = [row['student_id'] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(plan['students']):
        raise ValueError('Terminal roster does not match the frozen plan')
    result = {}
    for row in rows:
        name = row['student_id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or row['status'] not in terminal:
            raise ValueError('Invalid or nonterminal student record')
        result[name] = frozen_grade(run / f'student-{name}') if row['status'] == 'submitted' else None
    return result


def evaluate(run: Path, directory: Path) -> dict:
    # Complete every terminal/hash check before opening any reference file.
    grades = terminal_grades(run)
    if not grades or not any(grade is not None for grade in grades.values()):
        return {'verdict': 'infrastructure_incomplete', 'labels_loaded': False, 'score': None}
    ref = reference(directory)
    reports = {}
    for name, grade in grades.items():
        if grade is None:
            reports[name] = {'verdict': 'infrastructure_incomplete', 'score': None}
            continue
        report = compare(grade, ref)
        groups = {}
        actual = {row['item_id']: row for row in grade['items']}
        for row in ref['items']:
            groups.setdefault(row['question_id'], []).append(row)
        report['questions'] = []
        for question, rows in groups.items():
            expected = sum(row['score'] for row in rows)
            values = [actual.get(row['item_id'], {}).get('score') for row in rows]
            score = None if any(v is None for v in values) else sum(values)
            report['questions'].append({'question_id': question, 'reference': expected,
                                        'actual': score, 'matches': score == expected})
        reports[name] = report
    passed = all(row['verdict'] == 'pass' for row in reports.values())
    return {'verdict': 'M2 fixture regression pass' if passed else 'M2 fixture regression fail',
            'mode': 'posthoc evaluation', 'labels_loaded': True, 'students': reports,
            'scope': 'Known fixture only; no generalization or production-readiness claim.'}
