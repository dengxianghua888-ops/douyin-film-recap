#!/usr/bin/env python3
"""Build a byte-preserving core and linked evidence-text bundle in a new directory.

This is not a host installer. Historical external resources remain explicitly external.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
_RESOURCE_SPEC = importlib.util.spec_from_file_location('portable_resource_edges', Path(__file__).with_name('resource_edges.py'))
_resource_module = importlib.util.module_from_spec(_RESOURCE_SPEC)
_RESOURCE_SPEC.loader.exec_module(_resource_module)
resource_closure = _resource_module.closure
GROUPS = ('atomic', 'workflows', 'styles', 'contracts', 'runtime', 'registry', 'scripts', 'provenance', 'skills', '.codex-plugin')
PLUGIN_FILES = ('.mcp.json',)
TEXT_TYPES = {'.md', '.json', '.jsonl', '.html', '.txt', '.py', '.mjs', '.js', '.cjs', '.yaml', '.yml', '.patch'}


def digest(file):
    h = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def local_target(origin, target):
    target = unquote(target.split('#', 1)[0].split('?', 1)[0]).strip('<>')
    if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
        return None
    candidate = (origin.parent / target).resolve()
    candidate.relative_to(ROOT)  # Reject links that escape the library root.
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError('UNRESOLVED_LIBRARY_LINK: ' + str(candidate))
    return candidate


def checked_binding(row):
    relative = Path(row['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('POLICY_PATH_MUST_BE_LIBRARY_RELATIVE')
    file = ROOT / relative
    if file.is_symlink() or not file.is_file() or digest(file) != row['sha256']:
        raise ValueError('POLICY_BINDING_MISMATCH: ' + str(relative))
    file.resolve().relative_to(ROOT.resolve())
    return file.resolve()


def policy_rules(policy):
    if policy is None:
        return {}, set()
    if policy.get('schema') != 'portable-distribution-policy/1':
        raise ValueError('INVALID_DISTRIBUTION_POLICY_SCHEMA')
    external = {}
    excluded = set()
    for row in policy.get('external_links', []):
        if not isinstance(row.get('reason'), str) or not row['reason'].strip():
            raise ValueError('EXTERNAL_REASON_REQUIRED')
        origin, target = checked_binding(row['from']), checked_binding(row['target'])
        if target.suffix in TEXT_TYPES:
            raise ValueError('TEXT_LINK_CANNOT_BE_EXTERNALIZED')
        key = (origin, target)
        if key in external:
            raise ValueError('DUPLICATE_EXTERNAL_LINK')
        external[key] = row
    for row in policy.get('excluded_files', []):
        if not isinstance(row.get('reason'), str) or not row['reason'].strip():
            raise ValueError('EXCLUSION_REASON_REQUIRED')
        target = checked_binding(row)
        if target in excluded:
            raise ValueError('DUPLICATE_EXCLUSION')
        excluded.add(target)
    return external, excluded


def markdown_targets(text):
    """Extract inline links outside literal code; not an HTML/fetch dependency parser."""
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\n'))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            lines.append('\n')
        elif marker and (marker[1][0] != '`' or '`' not in marker[2]):
            fence = (marker[1][0], len(marker[1]))
            lines.append('\n')
        else:
            lines.append(line)
    body = ''.join(lines)
    # CommonMark code spans close only on a run of exactly the opening length.
    runs = list(re.finditer(r'`+', body))
    spans = []
    i = 0
    while i < len(runs):
        start = runs[i]
        if start.start() and len(re.search(r'\\*$', body[:start.start()])[0]) % 2:
            i += 1
            continue
        close = next((j for j in range(i + 1, len(runs)) if len(runs[j][0]) == len(start[0])), None)
        if close is None:
            i += 1
            continue
        spans.append((start.start(), runs[close].end()))
        i = close + 1
    for start, end in reversed(spans):
        body = body[:start] + ' ' * (end - start) + body[end:]
    return re.findall(r'\]\(([^)]+)\)', body)


def discover(policy=None, external_records=None):
    allowed_external, excluded = policy_rules(policy)
    core = {p for group in GROUPS for p in (ROOT / group).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
            and p != ROOT / 'runtime/editing_runtime.py.orig'}
    for name in PLUGIN_FILES:
        item = ROOT / name
        if not item.is_file() or item.is_symlink():
            raise ValueError('PLUGIN_FILE_MISSING_OR_SYMLINK: ' + name)
        core.add(item)
    if not (ROOT / '.codex-plugin' / 'plugin.json').is_file():
        raise ValueError('PLUGIN_MANIFEST_MISSING')
    if any(p.is_symlink() for p in core):
        raise ValueError('SYMLINK_NOT_SUPPORTED')
    if core & excluded:
        raise ValueError('EXCLUDED_FILE_IN_CORE')
    files = set(core)
    queue = sorted(core)
    links = []
    seen_external = set()
    for file in queue:
        if file.suffix != '.md':
            continue
        for link_target in markdown_targets(file.read_text()):
            target = local_target(file, link_target)
            if target is None:
                continue
            if target in excluded:
                raise ValueError('EXCLUDED_FILE_REFERENCED: ' + str(target))
            if target.suffix not in TEXT_TYPES:
                key = (file.resolve(), target)
                if key not in allowed_external:
                    raise ValueError('LINKED_BINARY_REQUIRES_EXPLICIT_DISTRIBUTION: ' + str(target))
                if key not in seen_external and external_records is not None:
                    external_records.append(allowed_external[key])
                seen_external.add(key)
                continue
            links.append({'from': str(file.relative_to(ROOT)), 'target': str(target.relative_to(ROOT))})
            if target not in files:
                files.add(target)
                queue.append(target)
    if seen_external != set(allowed_external):
        raise ValueError('UNUSED_EXTERNAL_LINK_DECLARATION')
    return core, files, links


def historical_refs(files):
    """Inventory explicit file references without copying private paths or changing history."""
    refs = []
    def walk(value, origin, pointer='$'):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                raw = value['path']
                # Relative references in historical JSON are not all root-relative.
                # Resolve only an unambiguous existing interpretation, otherwise report unknown.
                candidates = [Path(raw)] if Path(raw).is_absolute() else [origin.parent/raw, ROOT/raw]
                candidates = list(dict.fromkeys(p.resolve() for p in candidates if p.is_file()))
                resolved = candidates[0] if len(candidates) == 1 else None
                bundled = resolved in files if resolved else False
                refs.append({'record': str(origin.relative_to(ROOT)), 'pointer': pointer,
                    'original_path': raw, 'expected_sha256': value['sha256'],
                    'availability': 'bundled' if bundled else 'external-or-unresolved',
                    'bundle_path': str(resolved.relative_to(ROOT)) if bundled else None,
                    'historical_identity_not_relocated': True})
            for key, item in value.items():
                walk(item, origin, pointer + '.' + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, origin, pointer + '[' + str(index) + ']')
    for file in sorted(files):
        if file.suffix == '.json':
            walk(json.loads(file.read_text()), file)
    return refs


def inventory(policy=None):
    external = []
    core, files, links = discover(policy, external)
    entries = [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p), 'bytes': p.stat().st_size, 'mode': p.stat().st_mode & 0o777,
                'role': 'core' if p in core else 'historical-evidence-text'} for p in sorted(files)]
    # Explicit external targets must never also be copied via another core path.
    if {ROOT/r['target']['path'] for r in external} & files:
        raise ValueError('EXTERNAL_TARGET_ALSO_BUNDLED')
    return core, files, links, external, entries


def inventory_resources(policy=None, resources=None):
    core, files, links, external, _ = inventory(policy)
    files, resource_edges = resource_closure(ROOT, files, resources)
    if {ROOT/r['target']['path'] for r in external} & files:
        raise ValueError('EXTERNAL_TARGET_ALSO_BUNDLED')
    entries = [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p), 'bytes': p.stat().st_size, 'mode': p.stat().st_mode & 0o777,
                'role': 'core' if p in core else 'historical-evidence-text' if p.suffix in TEXT_TYPES
                else 'declared-resource'} for p in sorted(files)]
    return core, files, links, external, entries, resource_edges


def resource_hash(resources):
    if resources is None:
        return None
    return hashlib.sha256(json.dumps(resources, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def build(destination, policy=None, resources=None):
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError('OUTPUT_ALREADY_EXISTS')
    # Inventory and reject missing source links before creating output.
    core, files, links, external, entries, resource_edges = inventory_resources(policy, resources)
    refs = historical_refs(files)
    destination.mkdir(parents=True, exist_ok=False)
    for row in entries:
        source, target = ROOT/row['path'], destination/row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(row['mode'])
        if (digest(source) != row['sha256'] or digest(target) != row['sha256']
                or source.stat().st_mode & 0o777 != row['mode']
                or target.stat().st_mode & 0o777 != row['mode']):
            raise ValueError('COPY_OR_SOURCE_DRIFT: ' + row['path'])
    for link in links:
        if not (destination/link['target']).is_file():
            raise ValueError('BUNDLE_LINK_MISSING: ' + link['target'])
    for edge in resource_edges:
        target = edge['target']
        if 'path' not in target:
            continue
        present = (destination/target['path']).is_file()
        if edge['decision'] == 'bundle' and (not present or digest(destination/target['path']) != target['sha256']):
            raise ValueError('BUNDLE_RESOURCE_MISSING_OR_DRIFTED: ' + target['path'])
        if edge['decision'] != 'bundle' and present:
            raise ValueError('NONBUNDLE_RESOURCE_COPIED: ' + target['path'])
    # Source or policy targets may have drifted while copying. Do not report success.
    policy_rules(policy)
    manifest = {'schema': 'editing-portable-bundle/1', 'status': 'BUILT_NOT_HOST_INSTALLED',
        'files': entries, 'core_files': len(core), 'evidence_text_files': len(files-core),
        'markdown_links': len(links), 'files_byte_verified': True,
        'file_modes_verified': True,
        'file_mode_scope': 'POSIX rwx bits only; no setuid/setgid/sticky or ACL certification',
        'external_markdown_links': len(external),
        'distribution_policy': policy,
        'resource_declaration': resources, 'resource_declaration_sha256': resource_hash(resources),
        'resource_edges': resource_edges,
        'installation_diagnostics': {'entry': 'scripts/install_doctor.py',
            'status': 'NOT_RUN_ON_TARGET',
            'command_template': 'python3 scripts/install_doctor.py --root /absolute/bundle --out /absolute/new-report.json',
            'scope': 'Read-only dependency inventory; run in the target environment after copying.'},
        'codex_plugin': {'manifest': '.codex-plugin/plugin.json', 'mcp': '.mcp.json',
            'gateway_skill': 'skills/editing-skill-library/SKILL.md',
            'status': 'BUNDLED_NOT_INSTALLED_OR_HOST_ACCEPTED'},
        'runtime_version': re.search(r"^VERSION = '([^']+)'", (ROOT/'runtime/editing_runtime.py').read_text(), re.M).group(1),
        'limits': ['No host installation, automatic discovery or production certification.',
          'Historical evidence is copied byte-for-byte; its original absolute paths are not rewritten.',
          'Explicit external Markdown links remain unresolved in the standalone bundle; use the recorded locator and verify hashes in an authorized workspace.',
          'Media, models, source archives and tool binaries referenced by historical evidence are external.',
          'Historical HTML may need external media assets; text-link closure is not offline viewer acceptance.',
          'Configure explicit tool paths and fresh task inputs. Do not execute old requests against user files.']}
    (destination/'bundle-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (destination/'external-evidence.json').write_text(json.dumps({'schema':'historical-reference-locator/1',
        'note':'An index, not download permission or proof of remote availability. No historical references were rewritten.',
        'references':refs,'markdown_links':external},ensure_ascii=False,indent=2)+'\n')
    return {k:manifest[k] for k in ['status','core_files','evidence_text_files','markdown_links','runtime_version']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--policy',type=Path)
    parser.add_argument('--resources',type=Path,help='SHA-bound restricted HTML/CSS/JS resource declaration')
    parser.add_argument('--plan-only',action='store_true',help='Write an exclusive inventory JSON; do not copy files or build a package')
    args=parser.parse_args()
    policy = json.loads(args.policy.read_text()) if args.policy else None
    resources = json.loads(args.resources.read_text()) if args.resources else None
    if args.plan_only:
        if args.out.exists(): raise FileExistsError('OUTPUT_ALREADY_EXISTS')
        core, files, links, external, entries, resource_edges = inventory_resources(policy, resources)
        plan = {'schema':'portable-inventory/1','status':'INVENTORIED_NOT_BUILT_OR_RIGHTS_CERTIFIED',
                'files':entries,'core_files':len(core),'evidence_text_files':len(files-core),
                'bundled_links':links,'external_links':external,'policy':policy,
                'resource_declaration':resources,'resource_declaration_sha256':resource_hash(resources),
                'resource_edges':resource_edges,
                'limits':['No package built, license certification, host installation or offline-viewer acceptance.',
                          'Restricted literal resource closure only; dynamic JS needs separate review.']}
        with args.out.open('x') as stream: json.dump(plan,stream,ensure_ascii=False,indent=2);stream.write('\n')
        print(json.dumps({'status':plan['status'],'files':len(files),'external_links':len(external)}))
    else:
        print(json.dumps(build(args.out,policy,resources),ensure_ascii=False))
