"""Build chapter navigation from current work evidence and explicit learning prompts.

Usage: python build_learning_page.py --spec /absolute/spec.json --output /absolute/page.html
All references use {path, sha256}. No content selection, answer grading or work mutation.
"""
import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import quote, urlsplit

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R/'runtime'))
from editing_runtime import fingerprint
from work_ops import load


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def verified(item):
    path=Path(item['path'])
    if not path.is_absolute() or not path.is_file() or sha(path)!=item['sha256']:
        raise ValueError('REFERENCE_MISMATCH: '+str(path))
    return path


def read(path):
    return json.loads(path.read_text())


def current(store):
    db=sqlite3.connect(Path(store).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try: return load(db)
    finally: db.close()


def build(spec_path, output):
    spec=read(spec_path)
    if spec.get('schema')!='learning-page/1': raise ValueError('SPEC_SCHEMA')
    sidecar=output.with_suffix('.bindings.json')
    if output.exists() or sidecar.exists(): raise ValueError('OUTPUT_EXISTS')
    editions={}; bindings=[]
    for e in spec['editions']:
        key=e['id']
        if not re.fullmatch(r'[a-z][a-z0-9-]*',key) or key in editions: raise ValueError('EDITION_ID')
        doc=read(verified(e['document'])); mapping=read(verified(e['evidence_map']))
        state=current(e['store']); video=verified(e['video']); receipt=read(verified(e['render_receipt']))
        doc_hash=fingerprint(doc)
        if state['version']!=e['version'] or state['document']!=doc: raise ValueError('STALE_WORK')
        if mapping.get('schema')!='evidence-map/1' or mapping['document_sha256']!=doc_hash: raise ValueError('STALE_EVIDENCE_MAP')
        rendered=receipt.get('result',{})
        if (receipt.get('status')!='SUCCEEDED' or receipt.get('operation')!='work-render'
            or rendered.get('version')!=e['version'] or rendered.get('document_sha256')!=doc_hash
            or rendered.get('video')!=e['video']): raise ValueError('RENDER_BINDING_MISMATCH')
        chapters={}
        for c in mapping['chapters']:
            if c['id'] in chapters or not all(math.isfinite(c[k]) for k in ['start','end']) or not 0<=c['start']<c['end']:
                raise ValueError('CHAPTER_RANGE')
            chapters[c['id']]=c
        editions[key]=(e,chapters,video)
        bindings.append({'id':key,'store':e['store'],'version':e['version'],'document':e['document'],
                         'video':e['video'],'render_receipt':e['render_receipt'],'evidence_map':e['evidence_map']})
    esc=lambda s:html.escape(str(s),quote=True)
    url=lambda p:quote(os.path.relpath(p,output.parent),safe='/')
    def jump(edition, chapter, label):
        if edition not in editions or chapter not in editions[edition][1]: raise ValueError('CHAPTER_UNKNOWN')
        seconds=editions[edition][1][chapter]['start']
        return f'<button type="button" data-edition="{edition}" data-time="{seconds:.8f}">{esc(label)}</button>'
    cards=[]
    for key,(e,chapters,video) in editions.items():
        nav=''.join(jump(key,c['id'],f'{int(c["start"])//60:02}:{int(c["start"])%60:02} · {c["title"]}') for c in chapters.values())
        prompts=[]
        for exercise in e['exercises']:
            local=jump(key,exercise['chapter_id'],'回看本版依据')
            revisit=exercise.get('revisit'); extra=''
            if revisit: extra=jump(revisit['edition_id'],revisit['chapter_id'],'回看案例详解')
            prompts.append(f'<li><p>{esc(exercise["prompt"])}</p><details><summary>展开参考提示</summary><p>{esc(exercise["hint"])}</p></details>{local}{extra}</li>')
        cards.append(f'<section id="{key}"><h2>{esc(e["label"])}</h2><p>{esc(e["purpose"])}</p><p class="scope">{esc(e["selection_note"])}</p>'
            f'<video id="video-{key}" controls preload="metadata" src="{url(video)}"></video><p id="status-{key}" class="status" aria-live="polite"></p>'
            f'<nav aria-label="{esc(e["label"])}章节">{nav}</nav><h3>先回忆，再看提示</h3><ol>{"".join(prompts)}</ol>'
            f'<details><summary>来源映射与作品版本</summary><p>版本 {esc(e["version"])}</p><a href="{url(Path(e["evidence_map"]["path"]))}">章节与来源映射</a> · '
            f'<a href="{url(Path(e["document"]["path"]))}">可编辑作品文档</a></details></section>')
    attributions=[]
    for a in spec['attributions']:
        if urlsplit(a['url']).scheme not in ['https','http']: raise ValueError('ATTRIBUTION_URL')
        attributions.append(f'<li><a href="{esc(a["url"])}">{esc(a["label"])}</a> — {esc(a["note"])}</li>')
    css='body{max-width:1060px;margin:36px auto;padding:0 20px;background:#fff;color:#202a32;font:17px/1.75 system-ui;letter-spacing:0;overflow-wrap:anywhere}h1{font-size:30px}section{border-top:1px solid #ccd4d4;padding:24px 0;margin:28px 0}video{display:block;width:100%;aspect-ratio:4/3;max-height:70vh;background:#111}button{display:inline-block;padding:9px 12px;margin:5px 8px 5px 0;border:1px solid #aab7b6;border-radius:7px;background:#edf5f2;color:#183a33;font:inherit;text-align:left;cursor:pointer}nav{display:grid;grid-template-columns:1fr 1fr;gap:4px}summary{cursor:pointer;color:#28584c}.scope{border-left:3px solid #b3893e;padding-left:14px}.status{min-height:1.5em;color:#36594f}li{margin-bottom:16px}a{color:#28584c}footer{font-size:14px}@media(max-width:700px){nav{grid-template-columns:1fr}}'
    js='''document.querySelectorAll('button[data-time]').forEach(b=>b.addEventListener('click',()=>{const v=document.getElementById('video-'+b.dataset.edition);document.querySelectorAll('video').forEach(x=>x.pause());const seek=()=>{v.currentTime=Number(b.dataset.time);document.getElementById('status-'+b.dataset.edition).textContent='已定位至 '+Number(b.dataset.time).toFixed(2)+' 秒，按播放开始观看';v.scrollIntoView({block:'center',behavior:'smooth'});};if(v.readyState>=1)seek();else v.addEventListener('loadedmetadata',seek,{once:true});}));'''
    page=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(spec["title"])}</title><style>{css}</style><main><h1>{esc(spec["title"])}</h1><p>{esc(spec["summary"])}</p><p><strong>适合谁：</strong>{esc(spec["audience"])}</p><p><strong>先修：</strong>{esc(spec["prerequisites"])}</p>{"".join(cards)}<footer><p>{esc(spec["limits"])}</p><ul>{"".join(attributions)}</ul></footer></main><script>{js}</script></html>'
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(page)
    result={'schema':'learning-page-binding/1','spec':{'path':str(spec_path),'sha256':sha(spec_path)},
            'generator':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
            'html':{'path':str(output),'sha256':sha(output)},'editions':bindings,
            'scope':'Current work, render and compiled chapter binding at generation time; no semantic or learner assessment.'}
    with sidecar.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=build(a.spec.resolve(),a.output.resolve())
    print(json.dumps({'html':result['html'],'editions':len(result['editions'])},ensure_ascii=False))
