#!/usr/bin/env python3
"""Verify the staged patch on throwaway copies; never edit input trees."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--accepted', required=True, type=Path)
    p.add_argument('--candidate', required=True, type=Path)
    p.add_argument('--staging', type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()
    accepted, candidate, staging = (x.resolve() for x in (args.accepted, args.candidate, args.staging))
    manifest = json.loads((staging / 'native-patch-manifest.json').read_text())
    patch = staging / manifest['patch_file']
    assert sha(patch) == manifest['patch_sha256'], 'Patch digest mismatch'
    paths = [entry['path'] for entry in manifest['files']]
    assert len(paths) == 3 and len(set(paths)) == 3
    before = {str(tree / rel): sha(tree / rel) for tree in (accepted, candidate) for rel in paths}
    for item in manifest['files']:
        assert before[str(accepted / item['path'])] == item['accepted_sha256']
        assert before[str(candidate / item['path'])] == item['candidate_sha256']
    commands = []
    with tempfile.TemporaryDirectory(prefix='roundtrip-', dir=staging) as temp:
        work = Path(temp)
        for rel in paths:
            dest = work / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(accepted / rel, dest)
        for command in (['git', 'apply', '--check', str(patch)],
                        ['git', 'apply', str(patch)],
                        ['git', 'apply', '--reverse', '--check', str(patch)],
                        ['git', 'apply', '--reverse', str(patch)]):
            result = subprocess.run(command, cwd=work, capture_output=True, text=True)
            commands.append({'argv': [('<staging>/' + patch.name) if arg == str(patch) else arg for arg in command],
                             'cwd': '<throwaway-native-tree>', 'returncode': result.returncode,
                             'stdout': result.stdout, 'stderr': result.stderr})
            assert result.returncode == 0, commands[-1]
            if command == ['git', 'apply', str(patch)]:
                forward = {rel: sha(work / rel) for rel in paths}
                assert all(forward[item['path']] == item['candidate_sha256'] for item in manifest['files'])
        reverse = {rel: sha(work / rel) for rel in paths}
        assert all(reverse[item['path']] == item['accepted_sha256'] for item in manifest['files'])
        assert sorted(str(x.relative_to(work)) for x in work.rglob('*') if x.is_file()) == sorted(paths)
    after = {path: sha(Path(path)) for path in before}
    assert before == after, 'Input native tree changed during verification'
    result = {'status': 'PASS', 'patch_sha256': sha(patch), 'file_count': len(paths),
              'forward_check': 'PASS', 'forward_application': 'PASS', 'forward_hashes': forward,
              'reverse_check': 'PASS', 'reverse_application': 'PASS', 'reverse_hashes': reverse,
              'native_inputs_unchanged': True, 'temporary_tree_removed': True,
              'new_builds_or_simulations': False,
              'command_path_rendering': 'Absolute execution paths are replaced with <staging> and <throwaway-native-tree> placeholders; command results and hashes are unchanged.',
              'commands': commands}
    (staging / 'native-patch-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'patch_sha256', 'file_count', 'native_inputs_unchanged')}))


if __name__ == '__main__':
    main()
