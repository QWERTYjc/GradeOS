"""Offline fixture CLI; execution remains in the existing Pi entrypoints."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.fixture_inputs import ROOT, fixture_directory, input_documents, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'prepare', 'evaluate'])
    parser.add_argument('--fixture')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    failed = False
    if args.command == 'check':
        from evals.fixture_evaluation import reference
        results = []
        for name in [args.fixture] if args.fixture else sorted(p.name for p in ROOT.iterdir() if p.is_dir()):
            directory = fixture_directory(name)
            docs = input_documents(directory)
            row = {'fixture': name, 'source_hashes': 'verified', 'pages': {r: len(d['pages']) for r, d in docs.items()}}
            if (directory / 'posthoc/contract.json').exists():
                ref = reference(directory)
                row.update(reference_items=len(ref['items']), reference_total=sum(r['score'] for r in ref['items']))
            else:
                row['evaluation_status'] = 'source-only; official item labels unavailable'
            results.append(row)
        if not args.fixture:
            from evals.medly_assets import check
            rows = check()
            results.append({'fixture': 'medly', 'source_hashes': 'verified', 'answers': len(rows),
                            'evaluation_status': 'source-only; separately bound examiner labels unavailable'})
        print(json.dumps({'mode': 'check-only', 'model_requests': 0, 'fixtures': results}, indent=2))
        return
    if not args.fixture:
        parser.error('--fixture is required')
    directory = fixture_directory(args.fixture)
    if args.command == 'prepare':
        if not args.output:
            parser.error('--output is required (must be new)')
        result = prepare(directory, args.output)
    else:
        if not args.run:
            parser.error('--run is required')
        if not (directory / 'posthoc/contract.json').exists():
            parser.error('This fixture has no official item labels; it cannot be scored as a labeled regression')
        from evals.fixture_evaluation import evaluate
        result = evaluate(args.run.resolve(), directory)
        target = args.output or args.run / 'fixture-evaluation.json'
        with target.open('x') as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
        if result['verdict'] != 'M2 fixture regression pass':
            failed = True
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
