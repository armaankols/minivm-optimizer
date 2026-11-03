#!/usr/bin/env python3
"""Combine archived measurements without reweighting or hiding holdouts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT/'records/join-costs'
    fixed = json.loads((folder/'after.json').read_text())['measurements']
    holdouts = json.loads((folder/'holdouts.json').read_text())['measurements']
    stale = [row for row in holdouts if row['name'] == 'stale_profile_distribution']
    assert len(fixed) == 19 and len(holdouts) == 10 and len(stale) == 1
    matching = [row for row in holdouts if row not in stale]
    collections = {'fixed_19': fixed, 'stale_profile_1': stale,
                   'fixed_plus_stale_20': fixed+stale, 'matching_holdouts_9': matching,
                   'all_holdouts_10': holdouts, 'all_measured_29': fixed+holdouts}
    output = {'policy': 'one execution per retained case; diagnostic unweighted totals, not an expected production cost',
              'sources': ['after.json', 'holdouts.json'], 'groups': {}}
    for name, rows in collections.items():
        cycles = {p: sum(row['policies'][p]['cycles'] for row in rows)
                  for p in ('previous', 'current', 'always_HJOIN', 'always_NLJOIN')}
        output['groups'][name] = dict(cases=len(rows), simple=cycles['previous'],
            refined=cycles['current'], refined_minus_simple=cycles['current']-cycles['previous'],
            always_HJOIN=cycles['always_HJOIN'], always_NLJOIN=cycles['always_NLJOIN'])
    path = folder/'combined.json'
    path.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
