#!/usr/bin/env python3
"""Local stdio MCP bridge to the existing Editing Skill Library runtime.

The server speaks newline-delimited JSON-RPC over stdio. It does not perform
remote model calls, select an editing host, or infer that a listed skill works.
"""
import json
import os
from pathlib import Path
import sys

VERSION = '0.1.0'
NAME = 'editing-skill-library'


def library_root():
    local = Path(__file__).resolve().parents[1]
    if (local / 'registry' / 'skills.json').is_file():
        return local
    configured = os.environ.get('EDITING_SKILL_LIBRARY_ROOT')
    if configured and Path(configured).is_absolute():
        root = Path(configured).resolve()
        if (root / 'registry' / 'skills.json').is_file():
            return root
    raise ValueError('LIBRARY_ROOT_UNAVAILABLE: integrate plugin at the library root or set EDITING_SKILL_LIBRARY_ROOT to an absolute library path')


def _tool_specs():
    # MCP ToolAnnotations are hints, not authorization or sandbox guarantees.
    # destructiveHint/idempotentHint are immaterial for read-only tools.
    return [
        {'name': 'diagnose_installation',
         'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                         'idempotentHint': True, 'openWorldHint': False},
         'description': 'Read-only target-environment dependency inventory. Presence is not host or media acceptance.',
         'inputSchema': {'type': 'object', 'properties': {
             'ffmpeg': {'type': 'string', 'description': 'Absolute executable path; optional.'},
             'ffprobe': {'type': 'string', 'description': 'Absolute executable path; optional.'},
             'bindings': {'type': 'object', 'description': 'Optional font/asr lock path+sha256 references.'},
             'request': {'type': 'object', 'description': 'Optional exact local runtime request for branch-specific diagnosis.'}},
             'additionalProperties': False}},
        {'name': 'list_skills',
         'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                         'idempotentHint': True, 'openWorldHint': False},
         'description': 'List the local registry entries and declared layer/status. Static enumeration only.',
         'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
        {'name': 'run_operation',
         # A fresh receipt directory does not confine all effects: requests may
         # update existing Work/provider stores and explicitly send paid calls.
         # Directory rejection is not a replay/resume or idempotency contract.
         'annotations': {'readOnlyHint': False, 'destructiveHint': True,
                         'idempotentHint': False, 'openWorldHint': True},
         'description': 'Run one existing atomic runtime request into a new directory under EDITING_SKILL_WORK_ROOT. May update existing stores or invoke external providers. No generic retry/resume guarantee; existing work directories are rejected. Requires explicit task authorization and separate authorization for paid provider calls.',
         'inputSchema': {'type': 'object', 'properties': {
             'request': {'type': 'object', 'description': 'Exact editing_runtime request object.'},
             'work_dir': {'type': 'string', 'description': 'New absolute work directory under configured work root.'},
             'ffmpeg': {'type': 'string', 'description': 'Optional absolute FFmpeg executable.'},
             'ffprobe': {'type': 'string', 'description': 'Optional absolute ffprobe executable.'}},
             'required': ['request', 'work_dir'], 'additionalProperties': False}},
    ]


def call_tool(name, arguments):
    if not isinstance(arguments, dict):
        raise ValueError('TOOL_ARGUMENTS_OBJECT_REQUIRED')
    root = library_root()
    if name == 'list_skills':
        if arguments:
            raise ValueError('UNKNOWN_TOOL_ARGUMENTS')
        registry = json.loads((root / 'registry' / 'skills.json').read_text())
        return {'schema': registry.get('schema'), 'entries': [
            {k: row.get(k) for k in ('id', 'layer', 'entry', 'status')}
            for row in registry['entries']], 'limit': 'Static registry listing; no installation, route or capability execution claim.'}
    if name == 'diagnose_installation':
        if set(arguments) - {'ffmpeg', 'ffprobe', 'bindings', 'request'}:
            raise ValueError('UNKNOWN_TOOL_ARGUMENTS')
        local_runtime = Path(__file__).resolve().parents[1] / 'runtime'
        diagnostic_runtime = root / 'runtime' if (root / 'runtime' / 'dependency_discovery.py').is_file() else local_runtime
        sys.path.insert(0, str(diagnostic_runtime))
        try:
            from dependency_discovery import inspect
            return inspect(root, ffmpeg=arguments.get('ffmpeg'), ffprobe=arguments.get('ffprobe'),
                           bindings=arguments.get('bindings'), request=arguments.get('request'))
        finally:
            sys.path.pop(0)
    if name == 'run_operation':
        if set(arguments) - {'request', 'work_dir', 'ffmpeg', 'ffprobe'}:
            raise ValueError('UNKNOWN_TOOL_ARGUMENTS')
        request, raw = arguments.get('request'), arguments.get('work_dir')
        if not isinstance(request, dict) or not isinstance(raw, str) or not Path(raw).is_absolute():
            raise ValueError('REQUEST_OBJECT_AND_ABSOLUTE_WORK_DIR_REQUIRED')
        configured = os.environ.get('EDITING_SKILL_WORK_ROOT')
        if not configured or not Path(configured).is_absolute():
            raise ValueError('WORK_ROOT_REQUIRED: set EDITING_SKILL_WORK_ROOT to an absolute exclusive work parent')
        work_root = Path(configured).resolve()
        work_dir = Path(raw).resolve()
        if work_dir == work_root or work_root not in work_dir.parents or work_dir.exists():
            raise ValueError('NEW_WORK_DIR_UNDER_CONFIGURED_ROOT_REQUIRED')
        sys.path.insert(0, str(root / 'runtime'))
        try:
            import editing_runtime as runtime
            receipt = runtime.run(request, work_dir, runtime.Tools(arguments.get('ffmpeg'), arguments.get('ffprobe')))
        finally:
            sys.path.pop(0)
        return {'status': receipt['status'], 'receipt': receipt,
                'receipt_path': str(work_dir / 'receipt.json'),
                'limit': 'Runtime execution only; no human audiovisual or host acceptance.'}
    raise ValueError('UNKNOWN_TOOL: ' + str(name))


def _response(identifier, result=None, error=None):
    value = {'jsonrpc': '2.0', 'id': identifier}
    if error is None:
        value['result'] = result
    else:
        value['error'] = error
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def serve():
    for line in sys.stdin:
        message = None
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError('JSON_RPC_OBJECT_REQUIRED')
            identifier = message.get('id')
            method = message.get('method')
            if identifier is None:
                continue  # Notifications never receive responses.
            if method == 'initialize':
                requested = message.get('params', {}).get('protocolVersion')
                protocol = requested if requested in ('2024-11-05', '2025-03-26', '2025-06-18') else '2025-03-26'
                _response(identifier, {'protocolVersion': protocol,
                    'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': NAME, 'version': VERSION}})
            elif method == 'ping':
                _response(identifier, {})
            elif method == 'tools/list':
                _response(identifier, {'tools': _tool_specs()})
            elif method == 'tools/call':
                params = message.get('params') or {}
                try:
                    output = call_tool(params.get('name'), params.get('arguments') or {})
                    _response(identifier, {'content': [{'type': 'text', 'text': json.dumps(output, ensure_ascii=False)}],
                                           'isError': output.get('status') in ('FAILED', 'BUNDLE_DIAGNOSTIC_IDENTITY_FAILED')})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    _response(identifier, {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True})
            else:
                _response(identifier, error={'code': -32601, 'message': 'Method not found'})
        except (ValueError, TypeError, KeyError) as exc:
            if isinstance(message, dict) and message.get('id') is not None:
                _response(message['id'], error={'code': -32600, 'message': str(exc)})
    return 0


if __name__ == '__main__':
    sys.exit(serve())
