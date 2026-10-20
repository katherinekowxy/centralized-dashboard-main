"""Run scenario conformance checks without opening Streamlit."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from demo.engine import SCENARIOS, analyze, evaluate, generate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', default='all', choices=['all', *[item['scenario_id'] for item in SCENARIOS]])
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--out', type=Path, help='Optional folder for reproducible scenario exports')
    args = parser.parse_args()
    scenarios = [item['scenario_id'] for item in SCENARIOS] if args.scenario == 'all' else [args.scenario]
    results = []
    for scenario in scenarios:
        dataset = generate_dataset(scenario, args.seed)
        analysis = analyze(dataset['readings'], dataset['events'])
        checks = evaluate(dataset, analysis)
        passed = bool(checks) and all(check['passed'] for check in checks)
        results.append({'scenario': scenario, 'seed': args.seed, 'passed': passed, 'checks': checks})
        count = sum(bool(check['passed']) for check in checks)
        print(f"{'PASS' if passed else 'FAIL'}  {scenario}: {count}/{len(checks)} checks")
        if args.out:
            folder = args.out / scenario
            folder.mkdir(parents=True, exist_ok=True)
            for key in ('readings', 'events'):
                rows = dataset[key]
                fields = list(dict.fromkeys(key for row in rows for key in row))
                with (folder / f'{key}.csv').open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
            for name, value in (('analysis', analysis), ('evaluation', checks), ('metadata', dataset['metadata']), ('ground-truth-evaluation-only', dataset['ground_truth'])):
                (folder / f'{name}.json').write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    if args.out:
        (args.out / 'suite-results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print('Simulation conformance only; these checks do not estimate real-site detection accuracy.')
    return 0 if all(result['passed'] for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
