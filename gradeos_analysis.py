"""Read-only adapter to the extracted GradeOS reporting functions. No model, DB or score writes."""
import argparse
from collections import Counter
from pathlib import Path
import hashlib
import json
import statistics

ROOT = Path(__file__).resolve().parent
from analytics import (
    _build_class_report, _build_student_summary, build_global_logic_review_audit,
)


def analyze(bundle):
    rubric = bundle['rubric']['artifact']
    rubric_items = {item['item_id']: item for item in rubric['items']}
    students = []
    for record in bundle['records']:
        grade = record.get('grade')
        student = {'student_id': record['student_id'], 'total_score': None,
                   'max_total_score': None, 'score_status': 'unavailable', 'question_details': []}
        if grade:
            student.update(total_score=grade['total_score'], max_total_score=grade['max_score'],
                           score_status='available' if grade['total_score'] is not None else 'unavailable')
            # Retain the real item granularity; never fabricate internal M/A decisions or quotations.
            for item in grade['items']:
                source = rubric_items[item['item_id']]
                student['question_details'].append({
                    'question_id': item['item_id'], 'score': item['score'], 'max_score': item['max_score'],
                    'feedback': f"Item {item['item_id']}: {source['criteria']}",
                    'scoring_point_results': [],
                })
        student['student_summary'] = _build_student_summary(student)
        students.append(student)
    available = [s for s in students if s['total_score'] is not None]
    native_class = _build_class_report(students)
    if not available:
        native_class.update(average_score=None, average_percentage=None, pass_rate=None,
                            summary='No complete numerical results; unavailable scores are not zero.')
    audit = build_global_logic_review_audit(available, {'questions': [
        {'question_id': item['item_id'], 'max_score': item['max_score'], 'scoring_points': []}
        for item in rubric['items']]})
    item_stats = []
    for item_id, source in rubric_items.items():
        observations = [(r['student_id'], next(i for i in r['grade']['items'] if i['item_id'] == item_id))
                        for r in bundle['records'] if r.get('grade')]
        known = [item['score'] for _, item in observations if item['score'] is not None]
        variants = Counter(item['score'] for _, item in observations)
        item_stats.append({'item_id': item_id, 'max_score': source['max_score'],
                           'score_distribution': {str(k): v for k, v in variants.items()},
                           'mean_score_rate': statistics.mean(known)/source['max_score'] if known else None,
                           'unknown_count': sum(item['score'] is None for _, item in observations),
                           'varies': len(variants) > 1,
                           'evidence_refs': [f'{sid}/{item_id}' for sid, _ in observations]})
    known_totals = [s['total_score'] for s in available]
    methods = []
    for method_id, function, relative in [
        ('gradeos.student_summary', '_build_student_summary', 'analytics.py'),
        ('gradeos.class_report', '_build_class_report', 'analytics.py'),
        ('gradeos.global_logic_audit', 'build_global_logic_review_audit', 'analytics.py'),
    ]:
        path = ROOT / relative
        methods.append({'method_id': method_id, 'function': function, 'source_path': str(path),
                        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'result_set_hash': bundle['result_set_hash'], 'methods': methods,
            'cohort_context': bundle['cohort_context'], 'gradeos_class_report': native_class,
            'gradeos_global_logic_audit': audit,
            'gradeos_student_summaries': [{'student_id': s['student_id'], 'summary': s['student_summary']} for s in students],
            'harness_repeatability': {'score_distribution': dict(Counter(known_totals)),
                'mean': statistics.mean(known_totals) if known_totals else None,
                'population_sd': statistics.pstdev(known_totals) if known_totals else None,
                'constant_items': sum(not item['varies'] for item in item_stats),
                'item_count': len(item_stats), 'items': item_stats},
            'coverage': {'requested_records': len(students), 'scored_records': len(available),
                'excluded_from_numeric_audit': [s['student_id'] for s in students if s['total_score'] is None],
                'granularity': 'score-detail item; not internal M/A point',
                'knowledge_mapping': 'Unavailable. GradeOS knowledge_points here are item-score proxies, not validated topic mastery.',
                'point_evidence_audit': ('Harness validates selected-route point coverage, arithmetic and unconditional dependencies. Saved point evidence remains model interpretation; GradeOS point-evidence audit is not invoked.' if any(item.get('point_decisions') for record in bundle['records'] for item in (record.get('grade') or {}).get('items', [])) else 'Not evaluated: no internal M/A ledger or literal evidence quotations supplied.'),
                'grade_bands': 'GradeOS internal A>=85/B>=70/C>=60/D>=50/E<50; not official exam grades.',
                'mastery_thresholds': 'Class-report weak<0.60 and strong>=0.85 apply to item score rates only.',
                'jev_error_taxonomy': 'Not invoked; no classification was invented.',
                'official_reference': 'Not provided to this analysis or the reporting agent.',
                'risk_calibration': 'Not evaluated; statistical outliers are review prompts, not calibrated Risk.'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.bundle.read_text())), ensure_ascii=False))
