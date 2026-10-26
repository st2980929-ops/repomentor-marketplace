#!/usr/bin/env python3
"""Bounded, read-only inventory. Never import or execute target repository code."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import stat

SKIP_DIRS = {'.git', '.hg', '.svn', 'node_modules', '.venv', 'venv', '__pycache__',
             'dist', 'build', 'target', 'vendor', '.learning', '.ssh', '.aws',
             '.azure', '.config', '.gnupg', '.kube'}
LANGUAGES = {'.py': 'Python', '.js': 'JavaScript', '.jsx': 'JavaScript',
             '.ts': 'TypeScript', '.tsx': 'TypeScript', '.java': 'Java',
             '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP',
             '.cs': 'C#', '.cpp': 'C++', '.c': 'C', '.kt': 'Kotlin',
             '.swift': 'Swift', '.sh': 'Shell'}
MANIFESTS = {'pyproject.toml', 'requirements.txt', 'setup.py', 'setup.cfg',
             'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
             'go.mod', 'go.sum', 'pom.xml', 'build.gradle', 'build.gradle.kts',
             'Cargo.toml', 'Cargo.lock', 'Gemfile', 'composer.json',
             'Dockerfile', '.python-version', '.nvmrc', 'uv.lock'}


def sensitive(name):
    n = name.lower()
    return (n.startswith('.env') or n in {'.npmrc', '.pypirc', '.netrc'}
            or any(s in n for s in ('secret', 'credential', 'id_rsa', 'id_ed25519'))
            or Path(n).suffix in {'.pem', '.key', '.p12', '.pfx', '.keystore'})


def scan(root, max_files=5000, max_entries=20000, max_depth=12,
         max_file_bytes=262144, max_hash_bytes=20971520):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('repository path must be a directory')
    if min(max_files, max_entries, max_depth, max_file_bytes, max_hash_bytes) < 1:
        raise ValueError('limits must be positive')
    files, manifests, docs, tests, licenses = [], [], [], [], []
    languages, skipped = collections.Counter(), collections.Counter()
    pending, visited, hashed = [(root, 0)], 0, 0
    incomplete, errors = False, []
    while pending:
        folder, depth = pending.pop()
        try:
            with os.scandir(folder) as entries:
                for item in entries:
                    visited += 1
                    if visited > max_entries or len(files) >= max_files:
                        incomplete = True
                        pending.clear()
                        break
                    path = Path(item.path)
                    if item.is_symlink():
                        skipped['symlink'] += 1
                        continue
                    if sensitive(item.name):
                        skipped['sensitive'] += 1
                        continue
                    if item.is_dir(follow_symlinks=False):
                        if item.name in SKIP_DIRS:
                            skipped['excluded_directory'] += 1
                        elif depth >= max_depth:
                            skipped['depth_limit'] += 1
                            incomplete = True
                        else:
                            pending.append((path, depth + 1))
                        continue
                    info = item.stat(follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        skipped['special_file'] += 1
                        continue
                    rel = path.relative_to(root).as_posix()
                    record = {'path': rel, 'bytes': info.st_size, 'sha256': None}
                    if info.st_size <= max_file_bytes and hashed + info.st_size <= max_hash_bytes:
                        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                        with os.fdopen(fd, 'rb') as stream:
                            data = stream.read(min(max_file_bytes, max_hash_bytes - hashed) + 1)
                        hashed += len(data)
                        if len(data) <= max_file_bytes and hashed <= max_hash_bytes:
                            record['sha256'] = hashlib.sha256(data).hexdigest()
                        else:
                            skipped['hash_limit'] += 1
                    else:
                        skipped['hash_limit'] += 1
                    files.append(record)
                    language = LANGUAGES.get(path.suffix.lower())
                    if language:
                        languages[language] += 1
                    lower = item.name.lower()
                    if item.name in MANIFESTS or lower.startswith('requirements'):
                        manifests.append(rel)
                    if lower.startswith(('readme', 'contributing')) or 'docs' in path.relative_to(root).parts:
                        docs.append(rel)
                    if lower.startswith(('license', 'copying', 'notice')):
                        licenses.append(rel)
                    if (any(p.lower() in {'test', 'tests', '__tests__'} for p in path.relative_to(root).parts)
                            or lower.startswith('test_') or lower.endswith(('_test.go', '.test.ts', '.spec.js'))):
                        tests.append(rel)
        except OSError as exc:
            # Do not print exception messages which might contain sensitive names.
            errors.append({'directory': folder.relative_to(root).as_posix(), 'type': type(exc).__name__})
            incomplete = True
    files.sort(key=lambda x: x['path'])
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'schema_version': 1, 'root': str(root), 'files': files,
            'language_file_counts': dict(languages.most_common()),
            'manifests': sorted(manifests), 'documentation': sorted(docs),
            'tests': sorted(tests), 'licenses': sorted(licenses),
            'inventory_truncated': incomplete, 'skipped': dict(skipped), 'errors': errors,
            'snapshot_sha256': digest, 'hashed_bytes': hashed,
            'snapshot_scope': 'listed regular non-sensitive files; null hashes are not content-verified',
            'limits': {'files': max_files, 'entries': max_entries, 'depth': max_depth,
                       'file_bytes': max_file_bytes, 'hash_bytes': max_hash_bytes},
            'limitations': ['extension counts are not language proportions or complexity',
                            'no code execution, dependency resolution or architecture inference',
                            'excluded and unhashed files are outside content snapshot']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    for flag, default in [('max-files', 5000), ('max-entries', 20000), ('max-depth', 12),
                          ('max-file-bytes', 262144), ('max-hash-bytes', 20971520)]:
        parser.add_argument('--' + flag, type=int, default=default)
    args = vars(parser.parse_args())
    path = args.pop('path')
    try:
        print(json.dumps(scan(path, **args), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'detail': 'invalid/unreadable path or limits'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
