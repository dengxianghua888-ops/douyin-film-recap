"""Small, explicit source inventory and package reference checks.

This is a restricted Markdown checker, not a CommonMark or JavaScript parser.
File dependencies, directory navigation and declared resources remain distinct.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote


MEMBERS_FILE = 'contracts/package-members.json'
TEXT_TYPES = {'.md', '.json', '.jsonl', '.html', '.htm', '.css', '.txt', '.py',
              '.mjs', '.js', '.cjs', '.yaml', '.yml', '.patch', '.toml', '.cpp', '.sh'}
TEXT_NAMES = {'LICENSE', 'NOTICE', 'COPYING', 'AUTHORS', '.gitignore', '.env.example'}
EXCLUDED_PARTS = {'.git', '__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache',
                  '.tox', '.venv', 'venv', 'node_modules', '.DS_Store'}
PACKAGE_MANIFESTS = ('bundle-manifest.json', 'plugin-package-manifest.json')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def excluded(relative):
    return (bool(set(relative.parts) & EXCLUDED_PARTS)
            or relative.suffix in {'.pyc', '.pyo', '.orig', '.bak', '.log', '.tmp'}
            or relative.name.endswith('~')
            or (relative.name.startswith('.env') and relative.name != '.env.example'))


def checked_path(root, relative, kind='file'):
    """Reject lexical escapes and every symlink below the supplied root."""
    root = root.resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or str(relative) in ('', '.'):
        raise ValueError('PACKAGE_RELATIVE_PATH_REQUIRED: ' + str(relative))
    if excluded(relative):
        raise ValueError('PACKAGE_MEMBER_EXCLUDED: ' + str(relative))
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('PACKAGE_SYMLINK_UNSUPPORTED: ' + str(relative))
    current.resolve().relative_to(root)
    valid = current.is_dir() if kind == 'directory' else current.is_file()
    if not valid:
        raise ValueError('PACKAGE_TARGET_MISSING: ' + str(relative))
    return current


def is_text(path):
    if path.suffix.lower() not in TEXT_TYPES and path.name not in TEXT_NAMES:
        return False
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('DECLARED_TEXT_ENCODING_INVALID: ' + str(path)) from exc
    if any(ord(char) < 32 and char not in '\t\n\r\f' for char in text):
        raise ValueError('DECLARED_TEXT_CONTENT_INVALID: ' + str(path))
    return True


def source_members(root):
    """Only checked-in declarations select sources; recursive disk dirt is ignored."""
    manifest = checked_path(root, MEMBERS_FILE)
    declaration = json.loads(manifest.read_text(encoding='utf-8'))
    names = declaration.get('files')
    if (declaration.get('schema') != 'editing-package-members/1'
            or not isinstance(names, list) or not all(isinstance(x, str) for x in names)
            or len(set(names)) != len(names) or MEMBERS_FILE not in names):
        raise ValueError('INVALID_PACKAGE_MEMBERS')
    result = set()
    for name in names:
        path = checked_path(root, name)
        if not is_text(path):
            raise ValueError('CORE_BINARY_REQUIRES_RESOURCE_DECLARATION: ' + name)
        result.add(path)
    return result


def package_files(root):
    """A built package's full inventory supersedes its source seed list."""
    if (root / 'build-incomplete.json').exists():
        raise ValueError('PACKAGE_BUILD_NOT_COMPLETE')
    present = [root / name for name in PACKAGE_MANIFESTS if (root / name).exists()]
    if len(present) > 1:
        raise ValueError('AMBIGUOUS_PACKAGE_MANIFEST')
    if not present:
        return source_members(root)
    manifest = json.loads(present[0].read_text(encoding='utf-8'))
    expected = ('editing-portable-bundle/1', 'BUILT_NOT_HOST_INSTALLED') if present[0].name == PACKAGE_MANIFESTS[0] else (
        'editing-codex-plugin-package/1', 'BUILT_NOT_INSTALLED')
    if (manifest.get('schema'), manifest.get('status')) != expected:
        raise ValueError('PACKAGE_BUILD_NOT_COMPLETE')
    files = manifest.get('files', [])
    result = set()
    for row in files:
        path = checked_path(root, row['path'])
        if (path in result or digest(path) != row['sha256'] or path.stat().st_size != row['bytes']
                or path.stat().st_mode & 0o777 != row['mode']):
            raise ValueError('PACKAGE_MEMBER_IDENTITY_MISMATCH: ' + row['path'])
        result.add(path)
    if not result:
        raise ValueError('PACKAGE_MEMBERS_REQUIRED')
    return result


def source_identity(root, rows):
    content = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()
    result = {'member_declaration_sha256': digest(root / MEMBERS_FILE),
              'members_sha256': hashlib.sha256(content).hexdigest(),
              'git_commit': None, 'git_worktree_clean': None}
    if (root / '.git').exists():
        try:
            commit = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                    capture_output=True, text=True, check=True, timeout=5)
            status = subprocess.run(['git', '-C', str(root), 'status', '--porcelain'],
                                    capture_output=True, text=True, check=True, timeout=5)
            result.update(git_commit=commit.stdout.strip(), git_worktree_clean=not bool(status.stdout))
        except (OSError, subprocess.SubprocessError):
            pass  # The candidate is still bound by the complete member hashes.
    return result


def markdown_body(text):
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
    runs = list(re.finditer(r'`+', body))
    spans = []
    index = 0
    while index < len(runs):
        start = runs[index]
        if start.start() and len(re.search(r'\\*$', body[:start.start()])[0]) % 2:
            index += 1
            continue
        close = next((j for j in range(index + 1, len(runs)) if len(runs[j][0]) == len(start[0])), None)
        if close is None:
            index += 1
            continue
        spans.append((start.start(), runs[close].end()))
        index = close + 1
    for start, end in reversed(spans):
        body = body[:start] + ' ' * (end - start) + body[end:]
    return body


def markdown_targets(text):
    body = markdown_body(text)
    if re.search(r'^ {0,3}\[[^\]]+\]:|\]\[[^\]]*\]|<(?:a|img|script|link|iframe|video|audio)\b', body, re.M | re.I):
        raise ValueError('UNSUPPORTED_MARKDOWN_REFERENCE_REQUIRES_REVIEW')
    return re.findall(r'\]\(([^)]+)\)', body)


def local_target(root, origin, target):
    target = unquote(target.split('#', 1)[0].split('?', 1)[0]).strip('<>')
    if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
        return None
    # Normalize '..' lexically, before checking each ancestor for symlinks.
    raw = origin.parent / target
    candidate = Path(os.path.abspath(raw))
    try:
        relative = candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError('PACKAGE_LINK_ESCAPES_ROOT: ' + target) from exc
    # Inspect the unnormalized spelling too: a symlink followed by '..' is unsafe.
    current = origin.parent
    for part in Path(target).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('PACKAGE_SYMLINK_UNSUPPORTED: ' + target)
    kind = 'directory' if candidate.is_dir() else 'file'
    return checked_path(root, relative, kind), kind


def reference_edges(root, files, external_pairs=()):
    files = set(files)
    external_pairs = set(external_pairs)
    edges = []
    for source in sorted(files):
        if source.suffix != '.md':
            continue
        for raw in markdown_targets(source.read_text(encoding='utf-8')):
            spelling = unquote(raw.split('#', 1)[0].split('?', 1)[0]).strip('<>')
            if spelling and not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', spelling):
                candidate = Path(os.path.abspath(source.parent / spelling))
                try:
                    pair = (str(source.relative_to(root)), str(candidate.relative_to(root)))
                except ValueError:
                    pair = None
                if pair in external_pairs:
                    if candidate.exists():
                        raise ValueError('EXTERNAL_RESOURCE_PRESENT_IN_PACKAGE: ' + str(candidate))
                    continue
            found = local_target(root, source, raw)
            if found is None:
                continue
            target, kind = found
            source_name, target_name = str(source.relative_to(root)), str(target.relative_to(root))
            if (source_name, target_name) in external_pairs:
                continue
            if kind == 'directory':
                if not any(target in member.parents for member in files):
                    raise ValueError('DIRECTORY_NAVIGATION_HAS_NO_MEMBERS: ' + target_name)
            elif target not in files:
                raise ValueError('PACKAGE_LINK_TARGET_NOT_MEMBER: ' + target_name)
            edges.append({'from': source_name, 'target': target_name, 'kind': kind})
    return edges


def declared_entries(root, files):
    """Check explicit executable/registry/plugin fields, without interpreting prose."""
    files = set(files)

    def require(name, directory=False):
        target = checked_path(root, name, 'directory' if directory else 'file')
        if directory:
            if not any(target in file.parents for file in files):
                raise ValueError('PACKAGE_ENTRY_DIRECTORY_EMPTY: ' + str(name))
        elif target not in files:
            raise ValueError('PACKAGE_ENTRY_NOT_MEMBER: ' + str(name))

    for name in ('README.md', 'AGENTS.md', 'LICENSES.md', 'scripts/mcp_server.py',
                 'scripts/install_doctor.py', 'scripts/verify_library.py',
                 'runtime/editing_runtime.py', 'runtime/dependency_discovery.py',
                 'docs/local-setup.md', 'skills/editing-skill-library/SKILL.md'):
        require(name)
    require('.codex-plugin/plugin.json')
    plugin = json.loads((root / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    require(plugin['skills'], directory=True)
    require(plugin['mcpServers'])
    mcp = json.loads((root / plugin['mcpServers']).read_text(encoding='utf-8'))
    for server in mcp['mcpServers'].values():
        arguments = server.get('args')
        if (not isinstance(arguments, list) or len(arguments) != 1
                or not isinstance(arguments[0], str) or not arguments[0].endswith('.py')):
            raise ValueError('PACKAGE_MCP_ARGUMENTS_REQUIRE_DECLARED_SCRIPT')
        require(arguments[0])
        if server.get('cwd') != '.':
            raise ValueError('PACKAGE_MCP_CWD_UNSUPPORTED')
    require('registry/skills.json')
    registry = json.loads((root / 'registry/skills.json').read_text(encoding='utf-8'))
    for row in registry['entries']:
        require(row['entry'])


def inventory_rows(root, files):
    return [{'path': str(p.relative_to(root)), 'sha256': digest(p),
             'bytes': p.stat().st_size, 'mode': p.stat().st_mode & 0o777}
            for p in sorted(files)]


def verify_rows(root, rows):
    for row in rows:
        path = checked_path(root, row['path'])
        if (digest(path) != row['sha256'] or path.stat().st_size != row['bytes']
                or path.stat().st_mode & 0o777 != row['mode']):
            raise ValueError('PACKAGE_SOURCE_OR_COPY_DRIFT: ' + row['path'])


def copy_members(root, destination, rows):
    for row in rows:
        source = checked_path(root, row['path'])
        target = destination / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        parent = target.parent
        while parent != destination:
            if parent.is_symlink():
                raise ValueError('PACKAGE_SYMLINK_UNSUPPORTED: ' + str(parent))
            parent = parent.parent
        # New output only. Never overwrite an existing member or follow a link.
        with source.open('rb') as input_stream, target.open('xb') as output_stream:
            shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)
        target.chmod(row['mode'])
    verify_rows(root, rows)
    verify_rows(destination, rows)


def validate_package(root, files, external_pairs=(), require_entries=True):
    for path in files:
        checked_path(root, path.relative_to(root))
    edges = reference_edges(root, files, external_pairs)
    if require_entries:
        declared_entries(root, files)
    return edges


def validate_structure(root, rows, external_pairs=()):
    """Run the copied checker before publishing a successful package manifest."""
    check_input = root / 'build-check-input.json'
    with check_input.open('x', encoding='utf-8') as stream:
        json.dump({'schema': 'editing-package-check/1', 'files': rows,
                   'external_links': sorted(external_pairs)}, stream)
    try:
        result = subprocess.run([sys.executable, '-I', '-B', str(root / 'scripts/verify_library.py'),
                                 'structure', '--inventory', str(check_input)],
                                cwd=root, text=True, capture_output=True, timeout=60)
    finally:
        check_input.unlink()
    try:
        report = json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError('PACKAGE_STRUCTURE_CHECK_INVALID_OUTPUT') from exc
    if result.returncode != 0 or report.get('status') != 'PASSED':
        raise ValueError('PACKAGE_STRUCTURE_CHECK_FAILED: ' + json.dumps(report, ensure_ascii=False))
    return report
