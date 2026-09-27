"""Explicit caption text/window coverage, not semantic or rendered readability QA."""


def coverage_check(request, directory, tools):
    from editing_runtime import exact_keys, require, fingerprint, span, number, write_json
    from work_ops import validate_document
    fields = ['operation', 'document', 'expected_document_sha256', 'requirements']
    exact_keys(request, fields, fields)
    doc = request['document']
    require(fingerprint(doc) == request['expected_document_sha256'], 'DOCUMENT_REVISION_CONFLICT')
    norm, cues, _ = validate_document(doc, tools)
    by_id = {cue['id']: cue for cue in cues}
    requirements = request['requirements']
    require(isinstance(requirements, list) and requirements, 'REQUIREMENTS_REQUIRED')
    ids, results = set(), []
    for item in requirements:
        keys = ['id', 'text', 'match', 'caption_ids', 'start', 'end', 'min_continuous_seconds']
        exact_keys(item, keys, keys)
        rid = item['id']
        require(isinstance(rid, str) and rid.strip() and rid not in ids, 'REQUIREMENT_ID_DUPLICATE_OR_EMPTY')
        ids.add(rid)
        text = item['text']
        require(isinstance(text, str) and text.strip(), 'REQUIRED_TEXT_EMPTY')
        require(item['match'] in ['exact', 'contains'], 'MATCH_MODE_UNSUPPORTED')
        selected = item['caption_ids']
        require(isinstance(selected, list) and selected and all(isinstance(x, str) for x in selected), 'CAPTION_IDS_REQUIRED')
        require(len(selected) == len(set(selected)), 'CAPTION_ID_DUPLICATE')
        require(all(x in by_id for x in selected), 'CAPTION_ID_UNKNOWN')
        start, end = span(item['start'], item['end'], norm['duration'])
        minimum = number(item['min_continuous_seconds'], 'min_continuous_seconds', 0)
        require(minimum <= end-start+1e-8, 'MINIMUM_EXCEEDS_WINDOW')
        matched, intervals = [], []
        for cid in selected:
            cue = by_id[cid]
            require((cue['text'] == text if item['match'] == 'exact' else text in cue['text']), 'CAPTION_TEXT_MISMATCH: '+cid)
            a, b = max(start, cue['start']), min(end, cue['end'])
            if b > a:
                intervals.append((a, b))
            matched.append({'id': cid, 'start': cue['start'], 'end': cue['end']})
        merged = []
        for a, b in sorted(intervals):
            if merged and a <= merged[-1][1]+1e-8:
                merged[-1][1] = max(b, merged[-1][1])
            else:
                merged.append([a, b])
        require(len(merged) == 1 and merged[0][0] <= start+1e-8 and merged[0][1] >= end-1e-8,
                'CAPTION_WINDOW_NOT_COVERED: '+rid)
        longest = max((b-a for a, b in merged), default=0)
        require(longest+1e-8 >= minimum, 'CONTINUOUS_DURATION_TOO_SHORT')
        results.append({'id': rid, 'text': text, 'match': item['match'], 'output_window': [start, end],
                        'caption_spans': matched, 'coverage': merged, 'continuous_seconds': longest})
    result = {'schema': 'caption-coverage/1', 'document_sha256': fingerprint(doc), 'status': 'COVERED',
              'requirements': results, 'matching': 'literal Unicode, case and punctuation preserved; no normalization',
              'rendered_visibility': 'NOT_RUN', 'semantic_review': 'NOT_RUN',
              'scope': 'Declared caption text and output-time coverage in WorkDocument only; no truth, speech, typography, OCR, legal or aesthetic inference.'}
    write_json(directory/'caption-coverage.json', result)
    return result
