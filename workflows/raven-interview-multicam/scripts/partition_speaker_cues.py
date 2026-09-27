#!/usr/bin/env python3
"""Partition explicitly timed speaker captions into a single non-overlapping lane.

No transcript inference, editorial selection, hold-duration choice or work writes.
All times are half-open integer frames in one caller-specified output clock.
"""
import argparse
import json
from pathlib import Path


def partition(request):
    if set(request) != {'cues', 'display_order'}:
        raise ValueError('REQUEST_FIELDS')
    cues, order = request['cues'], request['display_order']
    if not isinstance(cues, list) or not cues or not isinstance(order, list):
        raise ValueError('CUES_AND_ORDER_REQUIRED')
    fields = {'id', 'speaker', 'text', 'speech_start_frame', 'speech_end_frame',
              'display_start_frame', 'display_end_frame'}
    ids = []
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != fields:
            raise ValueError('CUE_FIELDS')
        if any(not isinstance(cue[k], str) or not cue[k].strip() for k in ['id', 'speaker', 'text']):
            raise ValueError('IDENTITY_AND_TEXT_REQUIRED')
        if any(type(cue[k]) is not int or cue[k] < 0 for k in fields if k.endswith('_frame')):
            raise ValueError('NONNEGATIVE_INTEGER_FRAMES_REQUIRED')
        a, b = cue['speech_start_frame'], cue['speech_end_frame']
        s, e = cue['display_start_frame'], cue['display_end_frame']
        if not (a < b and a <= s < e and b <= e):
            raise ValueError('INVALID_OR_ANTICIPATORY_WINDOW')
        ids.append(cue['id'])
    if len(set(ids)) != len(ids):
        raise ValueError('DUPLICATE_ID')
    if any(not isinstance(x, str) for x in order) or len(order) != len(ids) or set(order) != set(ids):
        raise ValueError('EXPLICIT_TOTAL_ORDER_REQUIRED')
    rank = {key: i for i, key in enumerate(order)}
    bounds = sorted({c[k] for c in cues for k in ['display_start_frame', 'display_end_frame']})
    events = []
    for start, end in zip(bounds, bounds[1:]):
        active = sorted((c for c in cues if c['display_start_frame'] <= start < c['display_end_frame']),
                        key=lambda c: rank[c['id']])
        if not active:
            continue
        if len({c['speaker'] for c in active}) != len(active):
            raise ValueError('OVERLAPPING_SAME_SPEAKER_REQUIRES_CALLER_DECISION')
        events.append({'start_frame': start, 'end_frame': end,
                       'source_cue_ids': [c['id'] for c in active],
                       'text': '\n'.join(c['speaker'] + ': ' + c['text'] for c in active)})
    return {'schema': 'speaker-cue-partition/1', 'events': events,
            'scope': 'Explicit display windows only; no speech timing, readability or lip-sync certification.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = partition(json.loads(args.request.read_text()))
    with args.output.open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
