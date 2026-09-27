"""Compile explicit editorial records to source-bound historical meeting briefs.

No NLP classification, scheduling, messaging, audio generation or rendering.
The caller chooses status, scope, wording, fields and views; this checks literal bindings.
"""
import argparse
import datetime
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


LABELS={'recorded-consensus':'记录中的共识','process-decision':'流程决定','explicit-action':'明确后续行动',
        'proposed':'提议，未认证通过','deferred':'暂缓','unresolved':'仍待讨论'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def require(ok,code):
    if not ok:raise ValueError(code)


def date(value):
    require(isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value),'DATE_REQUIRED')
    return datetime.date.fromisoformat(value)


def checked_ref(item):
    p=Path(item['path'])
    require(p.is_absolute() and p.is_file() and sha(p)==item['sha256'],'SOURCE_HASH_MISMATCH')
    return p


def compile_brief(spec_path,out):
    spec=read(spec_path);require(spec['schema']=='meeting-brief/1','SCHEMA_UNSUPPORTED')
    require(spec['delivery']=='notes-only','NOTES_ONLY_REQUIRED')
    cutoff=date(spec['as_of']);require(not out.exists(),'OUTPUT_EXISTS')
    sources={};citations={};records={};views=[]
    for s in spec['sources']:
        require(s['id'] not in sources,'DUPLICATE_SOURCE')
        require(s['kind']=='published-meeting-minutes','SOURCE_KIND_UNSUPPORTED')
        require(date(s['meeting_date'])<=cutoff,'SOURCE_AFTER_CUTOFF')
        require(urlsplit(s['url']).scheme in ['http','https'],'SOURCE_URL_INVALID')
        p=checked_ref(s['file']);sources[s['id']]=(s,p.read_text().splitlines())
    for c in spec['citations']:
        require(set(c)=={'id','source_id','start_line','end_line','quote'},'CITATION_FIELDS')
        require(c['id'] not in citations and c['source_id'] in sources,'CITATION_ID')
        lines=sources[c['source_id']][1];a,b=c['start_line'],c['end_line']
        require(type(a) is int and type(b) is int and 1<=a<=b<=len(lines),'LINE_RANGE')
        require(c['quote']=='\n'.join(lines[a-1:b]),'QUOTE_MISMATCH')
        require(bool(c['quote'].strip()),'EMPTY_QUOTE')
        citations[c['id']]=c
    for row in spec['records']:
        require(re.fullmatch(r'[a-z][a-z0-9-]*',row['id']) and row['id'] not in records,'RECORD_ID')
        require(row['status'] in LABELS,'STATUS_UNSUPPORTED')
        require(bool(row['scope'].strip()) and bool(row['summary'].strip()),'SCOPE_AND_SUMMARY_REQUIRED')
        require(row['evidence'] and len(set(row['evidence']))==len(row['evidence']) and all(x in citations for x in row['evidence']),'EVIDENCE_REQUIRED')
        dates={sources[citations[x]['source_id']][0]['meeting_date'] for x in row['evidence']}
        require(dates=={row['meeting_date']},'RECORD_DATE_MISMATCH')
        require(all(x in row['evidence'] for x in row['confirmation']),'CONFIRMATION_NOT_IN_EVIDENCE')
        if row['status'] in ['recorded-consensus','process-decision','explicit-action']:
            require(bool(row['confirmation']),'CONFIRMATION_REQUIRED')
        for name in ['owner','deadline']:
            field=row[name]
            if field is not None:
                require(row['status']=='explicit-action','ACTION_FIELD_ON_NON_ACTION')
                require(set(field)=={'label','evidence'} and bool(field['label'].strip()) and field['evidence'],'FIELD_EVIDENCE_REQUIRED')
                require(all(x in row['evidence'] for x in field['evidence']),'FIELD_EVIDENCE_REQUIRED')
        require(all(isinstance(x,str) and x.strip() for x in row['cautions']),'CAUTION_TEXT_REQUIRED')
        records[row['id']]=row
    for row in records.values():
        require(len(set(row['requires']))==len(row['requires']) and all(x in records and x!=row['id'] for x in row['requires']),'CONTEXT_UNKNOWN_OR_SELF')
        require(all(date(records[x]['meeting_date'])<=date(row['meeting_date']) for x in row['requires']),'FUTURE_CONTEXT')
    seen=set()
    for v in spec['views']:
        require(re.fullmatch(r'[a-z][a-z0-9-]*',v['id']) and v['id'] not in seen,'VIEW_ID');seen.add(v['id'])
        require(v['style'] in ['decision-trace','action-handoff','open-question-ledger'],'VIEW_STYLE')
        require(v['record_ids'] and len(set(v['record_ids']))==len(v['record_ids']) and all(x in records for x in v['record_ids']),'VIEW_RECORDS')
        ids=set(v['record_ids'])
        require(all(set(records[x]['requires'])<=ids for x in ids),'VIEW_CONTEXT_OMITTED')
        views.append(v)
    # No partial documents are emitted for invalid declarations.
    out.mkdir(parents=True)
    esc=lambda x:html.escape(str(x),quote=True)
    artifacts=[]
    for v in views:
        heading=f'{v["title"]}（资料截止 {spec["as_of"]}）'
        md=[f'# {heading}', '', spec['scope'], '', v['purpose'], '',
            '这是历史会议记录的中文整理，不是当前规范、逐字转写或新任务指派。状态与概括由编辑者判断，校验只核对来源绑定。', '']
        sections=[];used=[]
        for rid in v['record_ids']:
            row=records[rid];label=LABELS[row['status']]
            md += [f'<a id="record-{rid}"></a>',f'## {row["topic"]} · {label} · {row["meeting_date"]}', '',row['summary'],'',f'范围：{row["scope"]}','']
            body=f'<h2>{esc(row["topic"])}</h2><p class="state">{esc(label)} · {esc(row["meeting_date"])}</p><p>{esc(row["summary"])}</p><p><b>范围：</b>{esc(row["scope"])}</p>'
            if row['status']=='explicit-action':
                owner=row['owner']['label'] if row['owner'] else '所选证据未明确执行负责人'
                deadline=row['deadline']['label'] if row['deadline'] else '所选证据未明确期限'
                md += [f'负责人：{owner}',f'期限：{deadline}','']
                body+=f'<p><b>负责人：</b>{esc(owner)}<br><b>期限：</b>{esc(deadline)}</p>'
            if row['requires']:
                md += ['必要上下文：'+', '.join(f'[{x}](#record-{x})' for x in row['requires']),'']
                body+='<p>必要上下文：'+', '.join(f'<a href="#record-{esc(x)}">{esc(records[x]["topic"])}</a>' for x in row['requires'])+'</p>'
            for caution in row['cautions']:
                md += ['- '+caution]
                body+=f'<p class="caution">{esc(caution)}</p>'
            md+=['','依据：'+', '.join(f'[{x}](#evidence-{x})' for x in row['evidence']),'']
            body+='<p>依据：'+', '.join(f'<a href="#evidence-{esc(x)}">{esc(x)}</a>' for x in row['evidence'])+'</p>'
            sections.append(f'<section id="record-{rid}">{body}</section>')
            used.extend(x for x in row['evidence'] if x not in used)
        evidence_html=[];md+=['## 来源摘录','']
        for cid in used:
            c=citations[cid];s=sources[c['source_id']][0]
            label=f'{s["meeting_date"]} 公开纪要 L{c["start_line"]}–{c["end_line"]}'
            md += [f'<a id="evidence-{cid}"></a>',f'### {cid} · [{label}]({s["url"]})','',
                   *('> '+line for line in c['quote'].splitlines()),'']
            evidence_html.append(f'<details id="evidence-{esc(cid)}"><summary>{esc(cid)} · {esc(label)}</summary><pre>{esc(c["quote"])}</pre><a href="{esc(s["url"])}">查看公开纪要</a></details>')
        md += ['来源版本与本地文件哈希见 bindings.json。仅对所选议题作整理，不宣称穷尽全部会议内容。','']
        mp=out/(v['id']+'.md');mp.write_text('\n'.join(md))
        css='body{max-width:1000px;margin:32px auto;padding:0 20px;font:17px/1.8 system-ui;color:#253334;overflow-wrap:anywhere}h1{font-size:30px}h2{font-size:22px}section{border-top:1px solid #ced8d4;padding:20px 0}.state{color:#285c50}.caution{border-left:3px solid #ba934f;padding-left:12px}a{color:#1c6656}details{margin:14px 0;padding:12px;background:#eff4f2}summary{cursor:pointer}pre{white-space:pre-wrap;font:14px/1.7 ui-monospace}nav a{display:inline-block;margin-right:16px}'
        nav=''.join(f'<a href="{x["id"]}.html">{esc(x["title"])}</a>' for x in views)
        hp=out/(v['id']+'.html');hp.write_text(f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(heading)}</title><style>{css}</style><nav>{nav}</nav><h1>{esc(heading)}</h1><p>{esc(spec["scope"])}</p><p>{esc(v["purpose"])}</p><p>历史资料整理；不代表当前规范或新任务指派。源为公开纪要，不是逐字音频。状态与概括由编辑者判断，技术校验不认证其语义。</p>{"".join(sections)}<h2>来源摘录</h2>{"".join(evidence_html)}<footer>仅对所选议题作整理，源版本与哈希见 bindings.json。</footer></html>')
        artifacts.extend({'path':str(p),'sha256':sha(p)} for p in [mp,hp])
    report={'schema':'meeting-brief-binding/1','status':'LITERAL_SOURCE_AND_DECLARED_CONTEXT_VERIFIED',
        'spec':{'path':str(spec_path),'sha256':sha(spec_path)},'helper':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
        'sources':spec['sources'],'as_of':spec['as_of'],'artifacts':artifacts,'records':len(records),'citations':len(citations),
        'semantic_review':'NOT_CERTIFIED','scope':'Exact source bytes, quotes, dates and caller-declared fields/context only; no approval classifier or task dispatch.'}
    (out/'bindings.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=compile_brief(a.spec.resolve(),a.output.resolve());print(json.dumps({'status':r['status'],'records':r['records'],'citations':r['citations']}))
