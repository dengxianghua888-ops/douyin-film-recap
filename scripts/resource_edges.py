"""Restricted, declared HTML/CSS/JS resource closure for portable bundles.

This is deliberately not a JavaScript dependency analyzer. Only literal forms below
are recognized; dynamic calls fail closed and other runtime loads need review.
"""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

RESOURCE_TYPES = {'.html', '.htm', '.css', '.js', '.mjs', '.cjs'}
JS_CALL = re.compile(r'\b(?:fetch|import)\s*\(\s*([^)]*)\)|\bnew\s+URL\s*\(\s*([^,)]*)', re.S)
JS_STATIC = re.compile(r'\b(?:import|export)\s+(?:[^;\n]*?\s+from\s+)?[\'\"]([^\'\"\n]+)[\'\"]')
CSS_URL = re.compile(r'url\(\s*[\'\"]?([^\'\")\s]+)[\'\"]?\s*\)|@import\s+[\'\"]([^\'\"\n]+)[\'\"]', re.I)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HTMLRefs(HTMLParser):
    def __init__(self):
        super().__init__(); self.refs = []; self.scripts = []; self.styles = []; self.active = None

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.active = tag
        for name, value in attrs:
            if not value:
                continue
            if name in ('src', 'href', 'poster', 'data'):
                self.refs.append(value)
            elif name == 'srcset':
                self.refs.extend(part.strip().split()[0] for part in value.split(',') if part.strip())

    def handle_data(self, data):
        if self.active == 'script': self.scripts.append(data)
        elif self.active == 'style': self.styles.append(data)

    def handle_endtag(self, tag):
        if tag == self.active: self.active = None


def css_references(text):
    return {ref for a, b in CSS_URL.findall(text) if (ref := a or b) and not ref.startswith(('data:', '#'))}


def js_references(text, path, reject_dynamic=True):
    refs = set(JS_STATIC.findall(text))
    for match in JS_CALL.finditer(text):
        expr = (match.group(1) or match.group(2)).strip()
        literal = re.match(r'^[\'\"]([^\'\"\n]+)[\'\"](?:\s*,|\s*$)', expr)
        if not literal:
            if reject_dynamic:
                raise ValueError('DYNAMIC_JS_RESOURCE_REQUIRES_REVIEW: ' + str(path))
            continue
        refs.add(literal.group(1))
    return refs


def dynamic_expressions(text):
    result = set()
    for match in JS_CALL.finditer(text):
        expr = (match.group(1) or match.group(2)).split(',', 1)[0].strip()
        if not re.match(r'^[\'\"]([^\'\"\n]+)[\'\"](?:\s*,|\s*$)', expr):
            result.add(expr)
    return result


def source_dynamic_expressions(path):
    text = path.read_text(encoding='utf-8')
    if path.suffix in ('.html', '.htm'):
        parser = HTMLRefs(); parser.feed(text)
        result = set()
        for script in parser.scripts:
            result.update(dynamic_expressions(script))
        return result
    return dynamic_expressions(text) if path.suffix in ('.js', '.mjs', '.cjs') else set()


def references(path, reject_dynamic=True):
    text = path.read_text(encoding='utf-8')
    if path.suffix in ('.html', '.htm'):
        parser = HTMLRefs(); parser.feed(text)
        refs = {ref for ref in parser.refs if not ref.startswith(('#', 'data:'))}
        for script in parser.scripts:
            refs.update(js_references(script, path, reject_dynamic))
        for style in parser.styles:
            refs.update(css_references(style))
        return refs
    if path.suffix == '.css':
        return css_references(text)
    return js_references(text, path, reject_dynamic)


def checked(root, row):
    if not isinstance(row, dict) or not isinstance(row.get('path'), str):
        raise ValueError('RESOURCE_BINDING_REQUIRED')
    rel = Path(row['path'])
    if rel.is_absolute() or '..' in rel.parts or str(rel) in ('', '.'):
        raise ValueError('RESOURCE_PATH_MUST_BE_RELATIVE')
    path = root / rel
    if not path.is_file() or path.is_symlink():
        raise ValueError('RESOURCE_TARGET_MISSING_OR_UNSAFE: ' + str(rel))
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError('RESOURCE_TARGET_MISSING_OR_UNSAFE: ' + str(rel))
    if sha(path) != row.get('sha256'):
        raise ValueError('RESOURCE_BINDING_MISMATCH: ' + str(rel))
    return path.resolve()


def checked_dynamic_proof(root, source, call):
    proof = call.get('proof')
    if not isinstance(proof, dict):
        raise ValueError('DYNAMIC_PROOF_REQUIRED')
    targets = call.get('targets')
    if not isinstance(targets, list) or not targets:
        raise ValueError('DYNAMIC_TARGET_SET_REQUIRED')
    if proof.get('kind') == 'source_literal_set':
        literal = proof.get('literal')
        if not isinstance(literal, str) or literal not in source.read_text(encoding='utf-8'):
            raise ValueError('DYNAMIC_LITERAL_PROOF_MISMATCH')
        refs = proof.get('references')
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            raise ValueError('DYNAMIC_LITERAL_REFERENCES_INVALID')
        if any(ref not in literal for ref in refs):
            raise ValueError('DYNAMIC_LITERAL_TARGET_NOT_IN_SOURCE')
        expected = {(source.parent / ref).resolve() for ref in refs}
        expected_hashes = {}
        if proof.get('binding'):
            binding = checked(root, proof['binding'])
            data = json.loads(binding.read_text(encoding='utf-8'))
            for key in proof.get('binding_keys', []):
                record = data[key]
                expected_hashes[Path(record['path']).resolve()] = record['sha256']
            if set(expected_hashes) != expected:
                raise ValueError('DYNAMIC_BINDING_TARGET_SET_MISMATCH')
    elif proof.get('kind') == 'json_binding_set':
        binding = checked(root, proof.get('binding'))
        data = json.loads(binding.read_text(encoding='utf-8'))
        if (source.parent / data.get('root_from_pack', '')).resolve() != root.resolve():
            raise ValueError('DYNAMIC_BINDING_ROOT_MISMATCH')
        expected = set(); expected_hashes = {}
        for key in proof.get('collections', []):
            for record in data.get(key, []):
                target = (root / record['path']).resolve()
                expected.add(target); expected_hashes[target] = record['sha256']
        for key in proof.get('singletons', []):
            record = data[key]; target = (root / record['path']).resolve()
            expected.add(target); expected_hashes[target] = record['sha256']
    else:
        raise ValueError('DYNAMIC_PROOF_KIND_UNSUPPORTED')
    declared = {checked(root, row['target']) for row in targets}
    if len(declared) != len(targets) or declared != expected:
        raise ValueError('DYNAMIC_TARGET_SET_MISMATCH')
    if expected_hashes and any(row['target']['sha256'] != expected_hashes[checked(root, row['target'])]
                           for row in targets):
        raise ValueError('DYNAMIC_BINDING_HASH_MISMATCH')
    return targets


def closure(root, files, declaration):
    """Return (files, edges); every supported source and observed literal needs a bound row."""
    files = set(files)
    if declaration is None:
        if any(p.suffix in RESOURCE_TYPES for p in files):
            raise ValueError('RESOURCE_DECLARATION_REQUIRED')
        return files, []
    if declaration.get('schema') != 'portable-resource-edges/1':
        raise ValueError('INVALID_RESOURCE_SCHEMA')
    rows = declaration.get('sources')
    if not isinstance(rows, list):
        raise ValueError('RESOURCE_SOURCES_REQUIRED')
    sources = {}
    for row in rows:
        source = checked(root, row)
        if source in sources or source.suffix not in RESOURCE_TYPES:
            raise ValueError('DUPLICATE_OR_INVALID_RESOURCE_SOURCE')
        sources[source] = row
    seen = set(); edges = []; queue = sorted(p for p in files if p.suffix in RESOURCE_TYPES)
    while queue:
        source = queue.pop(0)
        if source in seen:
            continue
        seen.add(source)
        if source not in sources:
            raise ValueError('RESOURCE_SOURCE_UNDECLARED: ' + str(source.relative_to(root)))
        row = sources[source]
        if row.get('closure_status') == 'unclosed':
            if not str(row.get('unclosed_reason', '')).strip():
                raise ValueError('RESOURCE_UNCLOSED_REASON_REQUIRED')
            raise ValueError('RESOURCE_SOURCE_UNCLOSED: ' + str(source.relative_to(root)))
        if row.get('closure_status') not in (None, 'closed'):
            raise ValueError('RESOURCE_CLOSURE_STATUS_INVALID')
        dynamic = source_dynamic_expressions(source)
        calls = row.get('dynamic_calls', [])
        if not isinstance(calls, list) or {x.get('expression') for x in calls} != dynamic or len(calls) != len(dynamic):
            raise ValueError('DYNAMIC_CALL_SET_MISMATCH: ' + str(source.relative_to(root)))
        observed = references(source, reject_dynamic=False)
        declared = row.get('edges')
        if not isinstance(declared, list):
            raise ValueError('RESOURCE_EDGES_REQUIRED')
        by_ref = {}
        for edge in declared:
            ref = edge.get('reference')
            if not isinstance(ref, str) or ref in by_ref:
                raise ValueError('DUPLICATE_OR_INVALID_RESOURCE_EDGE')
            by_ref[ref] = edge
        if observed != set(by_ref):
            raise ValueError('RESOURCE_EDGE_SET_MISMATCH: ' + str(source.relative_to(root)))
        for ref, edge in by_ref.items():
            decision = edge.get('decision')
            if decision not in ('bundle', 'external', 'forbidden'):
                raise ValueError('RESOURCE_DECISION_REQUIRED')
            if decision != 'bundle' and not str(edge.get('reason', '')).strip():
                raise ValueError('RESOURCE_REASON_REQUIRED')
            parsed = urlsplit(ref)
            if parsed.scheme or parsed.netloc or ref.startswith('//'):
                if decision != 'external' or edge.get('target') != {'url': ref}:
                    raise ValueError('REMOTE_RESOURCE_MUST_BE_EXTERNAL')
                target = None
            else:
                target = checked(root, edge.get('target'))
                expected = (source.parent / unquote(parsed.path)).resolve()
                if target != expected:
                    raise ValueError('RESOURCE_EDGE_TARGET_MISMATCH')
                if decision == 'bundle':
                    if target not in files:
                        files.add(target)
                        if target.suffix in RESOURCE_TYPES:
                            queue.append(target)
                elif target in files:
                    raise ValueError('RESOURCE_NONBUNDLE_TARGET_COPIED')
            edges.append({'from': str(source.relative_to(root)), 'reference': ref,
                          'decision': decision, 'target': edge['target'], 'reason': edge.get('reason')})
        for call in calls:
            for item in checked_dynamic_proof(root, source, call):
                decision = item.get('decision')
                if decision not in ('bundle', 'external', 'forbidden'):
                    raise ValueError('RESOURCE_DECISION_REQUIRED')
                if decision != 'bundle' and not str(item.get('reason', '')).strip():
                    raise ValueError('RESOURCE_REASON_REQUIRED')
                target = checked(root, item['target'])
                if decision == 'bundle':
                    if target not in files:
                        files.add(target)
                        if target.suffix in RESOURCE_TYPES: queue.append(target)
                elif target in files:
                    raise ValueError('RESOURCE_NONBUNDLE_TARGET_COPIED')
                edges.append({'from': str(source.relative_to(root)),
                              'reference': 'dynamic:' + call['expression'],
                              'decision': decision, 'target': item['target'],
                              'reason': item.get('reason'), 'proof': call['proof']})
    if seen != set(sources):
        raise ValueError('UNUSED_RESOURCE_SOURCE_DECLARATION')
    return files, edges
