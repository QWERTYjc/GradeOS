"""Posthoc item evaluation. This program is never imported by the grading harness."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def remap_ids(grade, mapping):
    original = {x['item_id'] for x in grade['items']}
    if set(mapping) != original or not all(isinstance(v, str) for v in mapping.values()):
        raise ValueError('ID map must cover every submitted ID exactly')
    if len(set(mapping.values())) != len(mapping):
        raise ValueError('ID map is not one-to-one')
    result = copy.deepcopy(grade)
    for row in result['items']:
        row['item_id'] = mapping[row['item_id']]
    return result


def compare(grade, reference):
    actual = {x['item_id']: x for x in grade['items']}
    if len(actual) != len(grade['items']):
        raise ValueError('Duplicate submitted item IDs')
    expected = {x['item_id']: x for x in reference['items']}
    if len(expected) != len(reference['items']):
        raise ValueError('Duplicate reference item IDs')
    rows = []
    for item_id, ref in expected.items():
        row = actual.get(item_id)
        score = row['score'] if row else None
        maximum_matches = bool(row and row['max_score'] == ref['max_score'])
        rows.append({'item_id': item_id, 'reference': ref['score'], 'actual': score,
                     'max_score': ref['max_score'], 'maximum_matches': maximum_matches,
                     'delta': None if score is None else score - ref['score'],
                     'matches': score == ref['score'] and maximum_matches})
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    known_total = None if any(x['score'] is None for x in grade['items']) else sum(x['score'] for x in grade['items'])
    max_total = sum(x['max_score'] for x in grade['items'])
    arithmetic_valid = grade['total_score'] == known_total and grade['max_score'] == max_total
    return {'verdict': 'pass' if not missing and not extra and arithmetic_valid and all(x['matches'] for x in rows) else 'fail',
            'reference_total': sum(x['score'] for x in reference['items']),
            'raw_item_total': known_total, 'host_total': grade['total_score'],
            'reviewed_total': None, 'matched_items': sum(x['matches'] for x in rows),
            'item_count': len(rows), 'missing_items': missing, 'extra_items': extra,
            'arithmetic_valid': arithmetic_valid,
            'absolute_item_error': None if any(x['delta'] is None for x in rows) else sum(abs(x['delta']) for x in rows),
            'items': rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--id-map', type=Path)
    args = parser.parse_args()
    summary = json.loads((args.run / 'summary.json').read_text())
    grading = args.run / 'grading.json'
    if summary['status'] not in ['submitted', 'completed'] or not grading.exists():
        result = {'verdict': 'infrastructure_incomplete', 'score': None,
                  'failure': summary.get('failure'), 'labels_loaded': False}
    else:
        data = grading.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != (args.run / 'grading.sha256').read_text().strip():
            raise ValueError('Frozen grade hash mismatch')
        reference_data = args.reference.read_bytes()
        grade = json.loads(data)
        mapping = json.loads(args.id_map.read_text()) if args.id_map else None
        if mapping is not None:
            grade = remap_ids(grade, mapping)
        result = compare(grade, json.loads(reference_data))
        if mapping is not None:
            result.update(item_id_mapping=mapping, normalization='Explicit posthoc identifier mapping only; frozen scores and evidence unchanged')
        result.update(grading_sha256=sha, reference_sha256=hashlib.sha256(reference_data).hexdigest(), labels_loaded=True)
    path = args.run / 'evaluation.json'
    with path.open('x') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'items'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
