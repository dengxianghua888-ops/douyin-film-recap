#!/usr/bin/env python3
"""Structure and immutable package manifests. Does not score creative quality."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PACKAGED = ('atomic','workflows','styles','contracts','runtime','registry','scripts','provenance')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files():
    return sorted(p for group in PACKAGED for p in (ROOT/group).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')


def structure():
    errors=[]; skills=[]
    for kind in ['atomic','workflows']:
        for entry in sorted((ROOT/kind).glob('*/SKILL.md')):
            text=entry.read_text()
            parts=text.split('---',2)
            if len(parts)!=3:errors.append(str(entry)+' frontmatter');continue
            name=re.search(r'^name:\s*(\S+)\s*$',parts[1],re.M)
            description=re.search(r'^description:\s*(.+)$',parts[1],re.M)
            if not name or name.group(1)!=entry.parent.name:errors.append(str(entry)+' name')
            if not description:errors.append(str(entry)+' description')
            skills.append({'id':entry.parent.name,'kind':kind,'entry':str(entry.relative_to(ROOT))})
    if len({s['id'] for s in skills})!=len(skills):errors.append('duplicate skill ID')
    links=0
    for p in files():
        if p.suffix!='.md':continue
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if target.startswith(('https://','http://','#')):continue
            link=unquote(target.split('#')[0])
            if not (p.parent/link).exists():errors.append(f'broken link: {p.relative_to(ROOT)} -> {target}')
            links+=1
    required=['id','name','family','fit','question','selection','sequence','audio','rhythm','visual','anti','example','nearest','effect_check','status','source_ids']
    style_counts={}
    for catalog_path in sorted((ROOT/'styles').glob('*/catalog.json')):
        catalog=json.loads(catalog_path.read_text());styles=catalog['styles'];ids=set()
        style_counts[catalog_path.parent.name]=len(styles)
        for style in styles:
            for key in required:
                if not style.get(key):errors.append(style.get('id','?')+' missing '+key)
            if style['id'] in ids:errors.append('duplicate style '+style['id'])
            ids.add(style['id'])
            if not (catalog_path.parent/f'{style["id"]}.md').is_file():errors.append('missing style card '+style['id'])
    registry=json.loads((ROOT/'registry/skills.json').read_text())
    entries=registry['entries'];known={s['id'] for s in skills}
    if {e['id'] for e in entries}!=known:errors.append('registry does not match actual skill entries')
    for entry in entries:
        if not (ROOT/entry['entry']).is_file():errors.append('registry missing entry '+entry['id'])
        for dep in entry.get('atomic_dependencies',[]):
            if dep not in known:errors.append('unknown dependency '+dep)
    return {'status':'FAILED' if errors else 'PASSED','skills':len(skills),'atomic_skills':sum(s['kind']=='atomic' for s in skills),
            'workflow_skills':sum(s['kind']=='workflows' for s in skills),'style_cards':sum(style_counts.values()),'style_families':style_counts,
            'local_links_checked':links,'errors':errors,'scope':'structure only; no routing or creative quality inference'}


def snapshot(path):
    if path.exists():raise ValueError('Snapshot exists; verify it, or use a distinct release filename')
    result=structure()
    if result['errors']:return result
    manifest={'schema':'library-manifest/1','scope':list(PACKAGED),'self_excluded':True,
              'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files()]}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(manifest,stream,ensure_ascii=False,indent=2)
    with path.with_suffix(path.suffix+'.sha256').open('x') as stream:stream.write(sha(path)+'\n')
    return {'status':'BASELINE_CREATED','files':len(manifest['files']),'manifest_sha256':sha(path),
            'scope':'local baseline creation, not proof of upstream authenticity or functional quality'}


def verify(path):
    failures=[]
    if sha(path)!=path.with_suffix(path.suffix+'.sha256').read_text().strip():failures.append('manifest hash mismatch')
    manifest=json.loads(path.read_text());expected={}
    for item in manifest['files']:
        rel=Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts:failures.append('invalid path '+str(rel));continue
        p=ROOT/rel;expected[str(rel)]=item
        if not p.is_file() or p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
            failures.append('missing or changed '+str(rel))
    for p in files():
        if str(p.relative_to(ROOT)) not in expected:failures.append('unexpected added file '+str(p.relative_to(ROOT)))
    return {'status':'FAILED' if failures else 'VERIFIED','files':len(expected),'errors':failures,
            'scope':'byte integrity against local baseline; no creative quality inference'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['structure','snapshot','verify'])
    parser.add_argument('--manifest',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='structure':result=structure()
        else:
            if not args.manifest:raise ValueError('--manifest required')
            result=snapshot(args.manifest) if args.command=='snapshot' else verify(args.manifest)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        sys.exit(1 if result.get('errors') else 0)
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps({'status':'FAILED','error':str(exc)},ensure_ascii=False));sys.exit(1)
