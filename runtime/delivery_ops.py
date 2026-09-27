"""Explicit, append-only selection of a verified strict-media work delivery.

This module records a technical selection. It does not certify listening,
player compatibility, a human edit, or publication readiness.
"""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from editing_runtime import ContractError, exact_keys, require, source
from tool_identity import inspect_tool
from work_ops import connect, load


def _head(db):
    current = load(db)
    return {k: current[k] for k in ('work_id', 'sequence', 'version', 'document_sha256')}


def _table_exists(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='delivery_events'").fetchone() is not None


def _create_table(db):
    db.execute('''CREATE TABLE IF NOT EXISTS delivery_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL CHECK(action IN ('select','restore','clear')),
        work_id TEXT NOT NULL,
        work_version TEXT NOT NULL,
        document_sha256 TEXT NOT NULL,
        prior_event_id INTEGER,
        target_event_id INTEGER,
        receipt_ref TEXT,
        binding_ref TEXT,
        media_ref TEXT,
        decision TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')


def _last(db):
    if not _table_exists(db):
        return None
    row = db.execute('SELECT * FROM delivery_events ORDER BY event_id DESC LIMIT 1').fetchone()
    return dict(row) if row is not None else None


def _event_ref(row, name):
    return json.loads(row[name]) if row[name] else None


def _read_ref(value, label):
    exact_keys(value, ['path', 'sha256'], ['path', 'sha256'])
    file = source(value)
    require(Path(file['path']).is_file(), label + '_MISSING')
    return json.loads(Path(file['path']).read_text(encoding='utf-8'))


def _strict_request_sha256(request):
    # strict_audio_freeze.execute uses json.dumps default ensure_ascii=True.
    payload = json.dumps(request, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(payload).hexdigest()


def _verified_pair(receipt_ref, binding_ref, head, store):
    receipt = _read_ref(receipt_ref, 'RECEIPT')
    binding = _read_ref(binding_ref, 'BINDING')
    require(receipt.get('schema') == 'strict-audio-freeze-receipt/1' and
            receipt.get('status') == 'SUCCEEDED' and receipt.get('operation') in ('create', 'verify'),
            'DELIVERY_RECEIPT_NOT_SUCCESS')
    require(receipt.get('work_delivery_binding') == binding_ref, 'DELIVERY_BINDING_RECEIPT_MISMATCH')
    require(binding.get('schema') == 'strict-work-delivery-binding/1' and
            binding.get('request_sha256') == receipt.get('request_sha256') and
            binding.get('script') == receipt.get('script') and
            binding.get('media') == receipt.get('media') and
            binding.get('current_at_finish') is True and
            binding.get('work_history_changed') is False and
            binding.get('verification', {}).get('status') == 'PASSED_EXACT_DECLARED_MEDIA_CONSTRAINTS',
            'DELIVERY_BINDING_INVALID')
    require(binding.get('store') == str(store) and
            all(binding.get(k) == head[k] for k in ('work_id', 'version', 'document_sha256')) and
            binding.get('sequence') == head['sequence'], 'DELIVERY_WORK_CONFLICT')
    require(receipt.get('work_at_finish') == {**head, 'store': str(store),
            'baseline': binding.get('baseline')}, 'DELIVERY_RECEIPT_WORK_CONFLICT')
    # The helper stores baseline in work_at_finish. Compare the full snapshot
    # separately, so a forged or stale binding cannot silently omit it.
    require(receipt.get('work_at_finish') == {
        k: binding.get(k) for k in ('store', 'work_id', 'sequence', 'version', 'document_sha256', 'baseline')
    }, 'DELIVERY_RECEIPT_WORK_CONFLICT')
    source(receipt['script'])
    request_path = Path(receipt_ref['path']).resolve().parent / 'request.json'
    commands_path = request_path.with_name('commands.json')
    require(request_path.is_file() and commands_path.is_file(), 'DELIVERY_EVIDENCE_INCOMPLETE')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    require(_strict_request_sha256(request) == receipt['request_sha256'] and
            request.get('work', {}).get('store') == str(store) and
            request.get('work', {}).get('expected_version') == head['version'],
            'DELIVERY_REQUEST_MISMATCH')
    chains = receipt.get('tool_chains')
    require(isinstance(chains, dict) and set(chains) == {'ffmpeg', 'ffprobe'} and
            chains == binding.get('tool_chains'), 'DELIVERY_TOOL_CHAIN_MISSING_OR_DIFFERENT')
    for name in ('ffmpeg', 'ffprobe'):
        configured = request.get('tools', {}).get(name)
        source(configured)
        current = inspect_tool(configured['path'], run_version=False)
        require(current['status'] == 'RESOLVED_EXECUTABLE_CHAIN' and
                current['identity_sha256'] == chains[name].get('identity_sha256'),
                'DELIVERY_TOOL_CHAIN_CHANGED: ' + name)
    require(isinstance(json.loads(commands_path.read_text(encoding='utf-8')), list), 'DELIVERY_COMMANDS_INVALID')
    media_ref = binding['media']
    source(media_ref)
    return media_ref


def _decision(value):
    exact_keys(value, ['actor', 'reason', 'review_refs'], ['actor', 'reason', 'review_refs'])
    require(value['actor'] in ('agent', 'human') and isinstance(value['reason'], str) and value['reason'].strip(),
            'DELIVERY_DECISION_REQUIRED')
    require(isinstance(value['review_refs'], list), 'DELIVERY_REVIEW_REFS_INVALID')
    for ref in value['review_refs']:
        source(ref)
    return value


def _insert(db, action, head, prior, target, receipt_ref, binding_ref, media_ref, decision):
    payload = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) if value is not None else None
    cursor = db.execute('''INSERT INTO delivery_events
        (action,work_id,work_version,document_sha256,prior_event_id,target_event_id,
         receipt_ref,binding_ref,media_ref,decision,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        (action, head['work_id'], head['version'], head['document_sha256'],
         prior, target, payload(receipt_ref), payload(binding_ref), payload(media_ref),
         payload(decision), datetime.now(timezone.utc).isoformat()))
    return cursor.lastrowid


def execute(request, directory=None, tools=None):
    require(request.get('operation') == 'work-delivery', 'UNSUPPORTED_OPERATION')
    action = request.get('action')
    common = ['operation', 'action', 'store']
    if action == 'read':
        exact_keys(request, common, common)
    elif action == 'select':
        exact_keys(request, common + ['expected_version', 'expected_event_id', 'receipt', 'binding', 'decision'],
                   common + ['expected_version', 'expected_event_id', 'receipt', 'binding', 'decision'])
    elif action == 'restore':
        exact_keys(request, common + ['expected_version', 'expected_event_id', 'target_event_id', 'decision'],
                   common + ['expected_version', 'expected_event_id', 'target_event_id', 'decision'])
    elif action == 'clear':
        exact_keys(request, common + ['expected_version', 'expected_event_id', 'decision'],
                   common + ['expected_version', 'expected_event_id', 'decision'])
    else:
        raise ContractError('DELIVERY_ACTION_UNSUPPORTED')
    store = Path(request['store']).resolve()
    require(Path(request['store']).is_absolute(), 'ABSOLUTE_STORE_PATH_REQUIRED')
    db = connect(store)
    try:
        db.execute('BEGIN' if action == 'read' else 'BEGIN IMMEDIATE')
        head = _head(db)
        last = _last(db)
        event_id = last['event_id'] if last else None
        if action == 'read':
            if last is None or last['action'] == 'clear':
                result = {'mode': 'RENDER_FALLBACK', 'reason': 'NO_CURRENT_SELECTION', 'event_id': event_id}
            elif last['work_id'] != head['work_id'] or last['work_version'] != head['version'] or last['document_sha256'] != head['document_sha256']:
                result = {'mode': 'RENDER_FALLBACK', 'reason': 'SELECTION_STALE_WORK_HEAD', 'event_id': event_id}
            else:
                try:
                    media = _verified_pair(_event_ref(last, 'receipt_ref'), _event_ref(last, 'binding_ref'), head, store)
                    require(media == _event_ref(last, 'media_ref'), 'DELIVERY_MEDIA_EVENT_MISMATCH')
                    result = {'mode': 'STRICT_MEDIA_TECHNICAL_CANDIDATE', 'event_id': event_id,
                              'media': media, 'publishable': False,
                              'review_status': 'NOT_VERIFIED_BY_THIS_OPERATION'}
                except (ContractError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    result = {'mode': 'RENDER_FALLBACK', 'reason': 'SELECTION_INVALID: ' + str(exc), 'event_id': event_id}
            db.rollback()
            return {'work': head, **result}
        require(request['expected_version'] == head['version'], 'WORK_VERSION_CONFLICT')
        require(request['expected_event_id'] is None or
                (type(request['expected_event_id']) is int and request['expected_event_id'] > 0),
                'DELIVERY_EVENT_ID_INVALID')
        require(request['expected_event_id'] == event_id, 'DELIVERY_SELECTION_CONFLICT')
        decision = _decision(request['decision'])
        if action == 'select':
            receipt_ref, binding_ref = request['receipt'], request['binding']
            media_ref = _verified_pair(receipt_ref, binding_ref, head, store)
            target = None
        elif action == 'restore':
            target = request['target_event_id']
            require(type(target) is int and target > 0 and _table_exists(db), 'DELIVERY_RESTORE_TARGET_REQUIRED')
            row = db.execute('SELECT * FROM delivery_events WHERE event_id=?', (target,)).fetchone()
            require(row is not None and row['action'] != 'clear', 'DELIVERY_RESTORE_TARGET_INVALID')
            receipt_ref, binding_ref = _event_ref(row, 'receipt_ref'), _event_ref(row, 'binding_ref')
            media_ref = _verified_pair(receipt_ref, binding_ref, head, store)
        else:
            receipt_ref = binding_ref = media_ref = target = None
        _create_table(db)
        next_id = _insert(db, action, head, event_id, target, receipt_ref, binding_ref, media_ref, decision)
        db.commit()
        return {'work': head, 'action': action, 'event_id': next_id, 'prior_event_id': event_id,
                'target_event_id': target, 'media': media_ref, 'mode': 'RENDER_FALLBACK' if action == 'clear' else 'STRICT_MEDIA_TECHNICAL_CANDIDATE',
                'publishable': False, 'history_preserved': True}
    except sqlite3.OperationalError as exc:
        db.rollback()
        raise ContractError('WORK_BUSY' if 'locked' in str(exc) else 'WORK_STORE_ERROR: ' + str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
