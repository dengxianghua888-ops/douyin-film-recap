"""Prepare an explicit leaf-field adoption; no editorial choice or work mutation.

Input: base/latest/donor WorkState snapshots plus selections [{path, resolution?}].
Path segments are dictionary keys or {id: stable_id} for list members. Only
existing scalar leaves are supported. Deletion, insertion and reordering remain
explicit timeline-revise operations. Resolutions: donor/latest, supplied upstream.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R/'runtime'))
from editing_runtime import fingerprint
from work_ops import token


def same(a, b):
    return fingerprint(a) == fingerprint(b)


def validate_state(state):
    digest = fingerprint(state['document'])
    if state['document_sha256'] != digest:
        raise ValueError('SNAPSHOT_DOCUMENT_HASH_MISMATCH')
    if state['version'] != token(state['work_id'], state['sequence'], digest):
        raise ValueError('SNAPSHOT_VERSION_MISMATCH')


def locate(document, path):
    if not isinstance(path, list) or not path:
        raise ValueError('NONEMPTY_FIELD_PATH_REQUIRED')
    current = document
    parent = key = None
    for segment in path:
        parent = current
        if isinstance(current, dict) and isinstance(segment, str):
            if segment not in current:
                raise ValueError('FIELD_MISSING: '+segment)
            key = segment
        elif isinstance(current, list) and isinstance(segment, dict) and set(segment)=={'id'}:
            if not isinstance(segment['id'], str) or not segment['id']:
                raise ValueError('STABLE_ID_REQUIRED')
            matches = [i for i, value in enumerate(current)
                       if isinstance(value, dict) and value.get('id')==segment['id']]
            if len(matches)!=1:
                raise ValueError('STABLE_ID_MISSING_OR_DUPLICATE: '+segment['id'])
            key = matches[0]
        else:
            raise ValueError('DICT_KEY_OR_STABLE_ID_REQUIRED; array indices are unsupported')
        current = parent[key]
    if isinstance(current, (dict, list)):
        raise ValueError('SCALAR_LEAF_REQUIRED; whole-object adoption unsupported')
    return parent, key, current


def prepare(request):
    if set(request) != {'base','latest','donor','selections'}:
        raise ValueError('EXACT_ADOPTION_FIELDS_REQUIRED')
    base, latest, donor = [request[k] for k in ('base','latest','donor')]
    for state in (base,latest,donor):
        validate_state(state)
    selections = request['selections']
    if not isinstance(selections,list) or not selections:
        raise ValueError('EXPLICIT_SELECTIONS_REQUIRED')
    candidate = copy.deepcopy(latest['document'])
    seen, rows, unresolved = set(), [], []
    for choice in selections:
        if not isinstance(choice,dict) or not set(choice)<= {'path','resolution'} or 'path' not in choice:
            raise ValueError('INVALID_SELECTION')
        path=choice['path']; identity=fingerprint(path)
        if identity in seen:
            raise ValueError('DUPLICATE_FIELD_PATH')
        seen.add(identity)
        b=locate(base['document'],path)[2]
        l=locate(latest['document'],path)[2]
        d=locate(donor['document'],path)[2]
        conflict=not same(l,b) and not same(l,d)
        resolution=choice.get('resolution')
        if resolution is not None and resolution not in ('donor','latest'):
            raise ValueError('RESOLUTION_MUST_BE_DONOR_OR_LATEST')
        if conflict and resolution is None:
            unresolved.append(path)
            action='unresolved'
        else:
            action=resolution or 'donor'
            parent,key,_=locate(candidate,path)
            parent[key]=copy.deepcopy(d if action=='donor' else l)
        rows.append({'path':path,'base':b,'latest':l,'donor':d,'conflict':conflict,'action':action})
    no_change = not unresolved and same(candidate, latest['document'])
    report={'schema':'field-adoption/1','status':'CONFLICT' if unresolved else 'ALREADY_SATISFIED' if no_change else 'PREPARED',
            'base_version':base['version'],'latest_version':latest['version'],'donor_version':donor['version'],
            'latest_document_sha256':latest['document_sha256'],'selections':rows,'unresolved_paths':unresolved,
            'document':None if unresolved else candidate,
            'document_sha256':None if unresolved else fingerprint(candidate),
            'applied_to_work':False,
            'lineage_validation':'snapshot content/token internally consistent; project identity, current revision and shared ancestry must be established from work history by caller',
            'next':('Resolve selected conflicts without committing.' if unresolved else
                    'Selected values already match latest; do not revise or commit.' if no_change else
                    'Run timeline-revise against this exact latest snapshot with explicit scope, then commit with expected_version; never patch version tokens to bypass conflicts.')}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    # Check output first so reruns cannot overwrite a reviewed conflict record.
    if args.output.exists():raise ValueError('OUTPUT_EXISTS')
    result=prepare(json.loads(args.request.read_text()))
    with args.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'applied_to_work':False}))
    return 2 if result['status']=='CONFLICT' else 0

if __name__=='__main__':sys.exit(main())
