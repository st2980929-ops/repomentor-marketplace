#!/usr/bin/env python3
"""Initialize and inspect Markdown learning state; never grade or advance tasks."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
TEMPLATES = {'PROJECT.md': 'project', 'PROJECT_ANALYSIS.md': 'analysis',
             'ARCHITECTURE.md': 'architecture', 'ROADMAP.md': 'roadmap',
             'PROGRESS.md': 'progress', 'KNOWLEDGE.md': 'knowledge',
             'DECISIONS.md': 'decisions', 'REPORT.md': 'report'}
MARKER = re.compile(r'(<!-- repo-mentor:data -->\s*```json\n)(.*?)(\n```\s*<!-- /repo-mentor:data -->)', re.S)
MODES = {'tutor', 'guided', 'demonstration'}
STATUSES = {'not_started', 'active', 'blocked', 'done', 'deferred'}


def read_text(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 262144:
        raise ValueError(f'invalid, linked, missing or oversized state file: {path.name}')
    return path.read_text(encoding='utf-8')


def metadata(text):
    blocks = list(MARKER.finditer(text))
    if len(blocks) != 1:
        raise ValueError('expected exactly one repo-mentor:data block')
    obj = json.loads(blocks[0].group(2))
    if not isinstance(obj, dict) or type(obj.get('schema_version')) is not int or obj['schema_version'] != 1:
        raise ValueError('unknown or missing state schema_version')
    return obj


def render(template, data=None):
    text = read_text(ASSETS / f'{template}-template.md')
    if data is not None:
        text = MARKER.sub(lambda m: m[1] + json.dumps(data, ensure_ascii=False, indent=2) + m[3], text)
    return text


def initialize(root, source_root=None, source_url=None, commit=None, name=None, mode='guided', brief=None):
    root = Path(root).resolve()
    if mode not in MODES:
        raise ValueError('invalid teaching mode')
    source = Path(source_root).resolve(strict=True) if source_root else None
    if source and (not source.is_dir() or source == root or source in root.parents or root in source.parents):
        raise ValueError('reference and learning directories must be disjoint')
    if not source and not source_url:
        raise ValueError('source-root or source-url is required')
    if commit and not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', commit):
        raise ValueError('commit must be a full verified commit hash, not a branch')
    brief_path = Path(brief).absolute() if brief else None
    if brief_path and brief_path.suffix.lower() != '.md':
        raise ValueError('brief must be a Markdown (.md) file')
    brief_text = read_text(brief_path) if brief_path else None
    # Prepare all content before making any writes.
    now = datetime.now(timezone.utc).isoformat()
    project = {'schema_version': 1, 'name': name or root.name, 'source_url': source_url,
               'source_root': str(source) if source else None, 'commit': commit,
               'learning_root': str(root), 'mode': mode, 'created_at': now,
               'brief_source': str(brief_path) if brief_path else None}
    progress = {'schema_version': 1, 'revision': 0, 'updated_at': now,
                'stage': None, 'task': None, 'step': 'discovery', 'status': 'not_started',
                'completed_tasks': [], 'pending_tasks': [], 'blockers': [],
                'next_action': '验证来源、完成分析与画像后制定路线，等待用户确认首任务',
                'awaiting_confirmation': True, 'confirmation': None}
    contents = {name: render(template, project if name == 'PROJECT.md' else progress if name == 'PROGRESS.md' else None)
                for name, template in TEMPLATES.items()}
    if brief_text is not None:
        contents['LEARNING_BRIEF.md'] = brief_text
    root.mkdir(exist_ok=True)
    target = root / '.learning'
    # mkdir is exclusive, including dangling symlinks; never replace any old state.
    target.mkdir()
    for filename, content in contents.items():
        with (target / filename).open('x', encoding='utf-8') as stream:
            stream.write(content)
    return {'created': str(target), 'files': sorted(contents), 'project': project, 'progress': progress}


def resume(root):
    root = Path(root).resolve(strict=True)
    state = root / '.learning'
    if state.is_symlink() or not state.is_dir():
        raise ValueError('no regular .learning directory; history is unavailable')
    docs = {name: read_text(state / name) for name in TEMPLATES}
    project, progress = metadata(docs['PROJECT.md']), metadata(docs['PROGRESS.md'])
    required_project = {'learning_root', 'mode', 'source_root', 'source_url', 'commit', 'name'}
    required_progress = {'revision', 'stage', 'task', 'step', 'status', 'completed_tasks',
                         'pending_tasks', 'blockers', 'next_action', 'awaiting_confirmation',
                         'confirmation', 'updated_at'}
    if not required_project <= project.keys() or not required_progress <= progress.keys():
        raise ValueError('required checkpoint fields missing')
    if (not isinstance(project['mode'], str) or project['mode'] not in MODES
            or not isinstance(progress['status'], str) or progress['status'] not in STATUSES):
        raise ValueError('unknown mode or status')
    for field in ('name', 'learning_root'):
        if not isinstance(project[field], str) or not project[field]:
            raise ValueError(f'invalid project field: {field}')
    for field in ('source_root', 'source_url', 'commit'):
        if project[field] is not None and not isinstance(project[field], str):
            raise ValueError(f'invalid project field: {field}')
    if not project['source_root'] and not project['source_url']:
        raise ValueError('source identity missing')
    if project['commit'] and not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', project['commit']):
        raise ValueError('invalid recorded commit hash')
    if project['learning_root'] != str(root):
        raise ValueError('learning directory moved; reconcile metadata explicitly')
    if project['source_root']:
        source = Path(project['source_root']).resolve()
        if source == root or source in root.parents or root in source.parents:
            raise ValueError('reference and learning directories overlap')
    if type(progress['awaiting_confirmation']) is not bool or type(progress['revision']) is not int or progress['revision'] < 0:
        raise ValueError('invalid checkpoint flag or revision')
    for field in ('completed_tasks', 'pending_tasks', 'blockers'):
        if not isinstance(progress[field], list) or any(not isinstance(v, str) for v in progress[field]):
            raise ValueError(f'{field} must be a string list')
    for field in ('stage', 'task'):
        if progress[field] is not None and not isinstance(progress[field], str):
            raise ValueError(f'{field} must be string or null')
    for field in ('step', 'next_action', 'updated_at'):
        if not isinstance(progress[field], str) or not progress[field]:
            raise ValueError(f'invalid checkpoint field: {field}')
    if progress['status'] == 'done' and not progress['awaiting_confirmation']:
        raise ValueError('completed task must await next-task confirmation')
    confirmation = progress['confirmation']
    if confirmation is not None:
        fields = {'from_task', 'to_task', 'user_request', 'at'}
        if not isinstance(confirmation, dict) or not fields <= confirmation.keys():
            raise ValueError('invalid confirmation record; required from_task/to_task/user_request/at')
        if confirmation['from_task'] is not None and not isinstance(confirmation['from_task'], str):
            raise ValueError('confirmation from_task must be string or null')
        if any(not isinstance(confirmation[f], str) or not confirmation[f] for f in ('to_task', 'user_request', 'at')):
            raise ValueError('invalid confirmation field values')
    if progress['status'] in {'active', 'done'}:
        if not progress['stage'] or not progress['task'] or confirmation is None:
            raise ValueError('active/completed task requires stage, task and recorded start confirmation')
        if confirmation['to_task'] != progress['task']:
            raise ValueError('recorded confirmation does not target the current task')
    brief_path = state / 'LEARNING_BRIEF.md'
    if brief_path.exists() or brief_path.is_symlink():
        docs['LEARNING_BRIEF.md'] = read_text(brief_path)
    return {'project': project, 'progress': progress,
            'documents': [{'path': str(state / name), 'sha256': hashlib.sha256(text.encode()).hexdigest()}
                          for name, text in docs.items()],
            'brief_present': 'LEARNING_BRIEF.md' in docs,
            'warning': 'Recorded checkpoint only: read documents and verify evidence; no tasks advanced or mastery inferred.'}


def discover(parent, max_depth=3, max_entries=2000):
    parent = Path(parent).resolve(strict=True)
    if not parent.is_dir() or min(max_depth, max_entries) < 1:
        raise ValueError('invalid search directory or limits')
    pending, found, count, truncated = [(parent, 0)], [], 0, False
    while pending:
        folder, depth = pending.pop()
        if (folder / '.learning').is_dir() and not (folder / '.learning').is_symlink():
            found.append(str(folder))
            continue
        try:
            with os.scandir(folder) as entries:
                for item in entries:
                    count += 1
                    if count > max_entries:
                        truncated = True
                        pending.clear()
                        break
                    if item.is_dir(follow_symlinks=False) and not item.is_symlink() and not item.name.startswith('.') and item.name not in {'node_modules', 'vendor'}:
                        if depth < max_depth:
                            pending.append((Path(item.path), depth + 1))
                        else:
                            truncated = True
        except OSError:
            truncated = True
    return {'candidates': sorted(found), 'selection_required': len(found) > 1,
            'search_truncated': truncated, 'root': str(parent)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('root')
    for arg in ('source-root', 'source-url', 'commit', 'name', 'brief'):
        init.add_argument('--' + arg)
    init.add_argument('--mode', choices=sorted(MODES), default='guided')
    sub.add_parser('resume').add_argument('root')
    find = sub.add_parser('discover')
    find.add_argument('parent')
    find.add_argument('--max-depth', type=int, default=3)
    find.add_argument('--max-entries', type=int, default=2000)
    args = vars(parser.parse_args())
    command = args.pop('command')
    try:
        result = {'init': initialize, 'resume': resume, 'discover': discover}[command](**args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'detail': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
