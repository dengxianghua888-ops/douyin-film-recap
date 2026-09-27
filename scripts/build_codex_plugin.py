#!/usr/bin/env python3
"""Build a small, runnable Codex plugin from the current library source.

The plugin contains current Skills, contracts, registry and runtime. Historical
evaluation assets are deliberately outside this executable package and retain
their original paths and evidence status in the main library.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
GROUPS = ('atomic', 'workflows', 'styles', 'contracts', 'runtime', 'registry',
          'scripts', 'provenance', 'skills', '.codex-plugin')
SINGLE_FILES = ('.mcp.json',)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory():
    files = set()
    for group in GROUPS:
        directory = ROOT / group
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError('PLUGIN_GROUP_MISSING_OR_SYMLINK: ' + group)
        for path in directory.rglob('*'):
            if ('__pycache__' in path.parts or path.suffix == '.pyc'
                    or path == ROOT / 'runtime/editing_runtime.py.orig'):
                continue
            if path.is_symlink():
                raise ValueError('PLUGIN_SYMLINK_UNSUPPORTED: ' + str(path))
            if path.is_file():
                files.add(path)
    for name in SINGLE_FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('PLUGIN_FILE_MISSING_OR_SYMLINK: ' + name)
        files.add(path)
    return [{'path': str(path.relative_to(ROOT)), 'sha256': digest(path),
             'bytes': path.stat().st_size, 'mode': path.stat().st_mode & 0o777}
            for path in sorted(files)]


def build(destination):
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError('PLUGIN_OUTPUT_ALREADY_EXISTS')
    rows = inventory()
    destination.mkdir(parents=True, exist_ok=False)
    for row in rows:
        source = ROOT / row['path']
        target = destination / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(row['mode'])
        if (digest(source) != row['sha256'] or digest(target) != row['sha256']
                or source.stat().st_mode & 0o777 != row['mode']
                or target.stat().st_mode & 0o777 != row['mode']):
            raise ValueError('PLUGIN_SOURCE_OR_COPY_DRIFT: ' + row['path'])
    manifest = {
        'schema': 'editing-codex-plugin-package/1',
        'status': 'BUILT_NOT_INSTALLED',
        'plugin_name': 'editing-skill-library',
        'files': rows,
        'file_modes_verified': True,
        'file_mode_scope': 'POSIX rwx bits only; no setuid/setgid/sticky or ACL certification',
        'historical_evaluation_assets': 'EXCLUDED; see authoritative source library',
        'native_editor_host': 'NOT_REQUIRED_FOR_GENERIC_SKILLS',
        'media_generation_provider': 'AGENT_OWNED_NOT_REQUIRED_FOR_SKILL_LOAD',
    }
    (destination / 'plugin-package-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'status': manifest['status'], 'path': str(destination),
            'files': len(rows), 'manifest_sha256': digest(destination / 'plugin-package-manifest.json')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True, help='New absolute output directory')
    args = parser.parse_args()
    if not args.out.is_absolute():
        raise ValueError('PLUGIN_OUTPUT_ABSOLUTE_PATH_REQUIRED')
    print(json.dumps(build(args.out), ensure_ascii=False))


if __name__ == '__main__':
    main()
