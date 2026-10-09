"""MCP declarations and real local effects; external sending uses a fake client."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('mcp_metadata_server', ROOT / 'scripts/mcp_server.py')
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)
HINTS = {
    'diagnose_installation': dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    'list_skills': dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    'run_operation': dict(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True),
}


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class MCPMetadataTests(unittest.TestCase):
    def exchange(self, messages):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith('EDITING_') and k != 'DEEPSEEK_API_KEY'}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/mcp_server.py')],
                                input=''.join(json.dumps(m) + '\n' for m in messages),
                                text=True, capture_output=True, env=env, timeout=60, check=True)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_tools_list_explicit_boolean_hints_on_wire(self):
        rows = self.exchange([{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}])
        specs = rows[0]['result']['tools']
        self.assertEqual({s['name']: s['annotations'] for s in specs}, HINTS)
        for spec in specs:
            self.assertTrue(all(type(v) is bool for v in spec['annotations'].values()))
            self.assertEqual(spec['inputSchema']['type'], 'object')

    def test_read_tools_repeat_without_credentials_or_file_changes(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            font = folder / 'font.ttf'
            font.write_bytes(b'diagnostic binding only')
            arguments = {'ffmpeg': str(folder / 'missing-ffmpeg'),
                         'ffprobe': str(folder / 'missing-ffprobe'),
                         'bindings': {'font': {'path': str(font), 'sha256': hashlib.sha256(font.read_bytes()).hexdigest()}}}
            before = snapshot(folder)
            messages = [{'jsonrpc': '2.0', 'id': i, 'method': 'tools/call',
                         'params': {'name': name, 'arguments': args}}
                        for i, (name, args) in enumerate([
                            ('list_skills', {}), ('diagnose_installation', arguments),
                            ('list_skills', {}), ('diagnose_installation', arguments)], 1)]
            rows = self.exchange(messages)
            self.assertTrue(all(not r['result']['isError'] for r in rows))
            self.assertEqual(rows[0]['result'], rows[2]['result'])
            self.assertEqual(rows[1]['result'], rows[3]['result'])
            self.assertEqual(snapshot(folder), before)
            self.assertTrue(json.loads(rows[0]['result']['content'][0]['text'])['entries'])

    def test_run_operation_writes_external_store_and_rejects_directory_replay(self):
        with tempfile.TemporaryDirectory() as raw, patch.dict(os.environ, {}, clear=True):
            folder = Path(raw)
            work = folder / 'runs'
            work.mkdir()
            os.environ['EDITING_SKILL_WORK_ROOT'] = str(work)
            ledger = folder / 'provider.sqlite'
            request = {'operation': 'model-text-deepseek', 'action': 'budget-create',
                       'store': str(ledger), 'budget_key': 'test', 'currency': 'USD', 'limit_micros': 100}
            args = {'request': request, 'work_dir': str(work / 'first')}
            result = server.call_tool('run_operation', args)
            self.assertEqual(result['status'], 'SUCCEEDED')
            self.assertTrue(ledger.is_file())  # Outside EDITING_SKILL_WORK_ROOT.
            self.assertTrue((work / 'first/request.json').is_file())
            self.assertTrue((work / 'first/receipt.json').is_file())
            before = snapshot(folder)
            with self.assertRaisesRegex(ValueError, 'NEW_WORK_DIR_UNDER_CONFIGURED_ROOT_REQUIRED'):
                server.call_tool('run_operation', args)
            self.assertEqual(snapshot(folder), before)
            # Fresh output directory is a new execution, even for a matching budget.
            args['work_dir'] = str(work / 'second')
            self.assertEqual(server.call_tool('run_operation', args)['status'], 'SUCCEEDED')
            self.assertTrue((work / 'second/receipt.json').is_file())
            # An existing ledger can also be updated, not just appended to.
            sys.path.insert(0, str(ROOT / 'runtime'))
            try:
                from deepseek_text import DeepSeekCallStore
                from deepseek_dispatch import DeepSeekTextClient
                store = DeepSeekCallStore(ledger)
                call = store.prepare('intent', {'model': 'test', 'messages': [{'role': 'user', 'content': 'synthetic'}],
                                               'max_tokens': 1}, 'test', 1)
                before_send = ledger.read_bytes()
                with patch('deepseek_dispatch.DeepSeekTextClient', autospec=DeepSeekTextClient) as client:
                    client.return_value.provider_id = 'deepseek'
                    client.return_value.base_url = 'https://api.deepseek.com'
                    client.return_value.send.return_value = {'choices': [], 'usage': {}}
                    sent = server.call_tool('run_operation', {'request': {'operation': 'model-text-deepseek',
                        'action': 'send-once', 'store': str(ledger), 'call_id': call['call_id']},
                        'work_dir': str(work / 'send')})
                    self.assertEqual(sent['status'], 'SUCCEEDED', sent)
                    client.return_value.send.assert_called_once()
                self.assertNotEqual(ledger.read_bytes(), before_send)
            finally:
                sys.path.pop(0)

    def test_work_directory_conflicts_do_not_execute(self):
        with tempfile.TemporaryDirectory() as raw, patch.dict(os.environ, {}, clear=True):
            folder = Path(raw)
            work = folder / 'runs'
            work.mkdir()
            os.environ['EDITING_SKILL_WORK_ROOT'] = str(work)
            occupied = work / 'occupied'
            occupied.mkdir()
            (occupied / 'manual.txt').write_text('preserve')
            before = snapshot(folder)
            for target in (work, occupied, folder / 'outside'):
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'NEW_WORK_DIR_UNDER_CONFIGURED_ROOT_REQUIRED'):
                    server.call_tool('run_operation', {'request': {'operation': 'invalid'}, 'work_dir': str(target)})
            self.assertEqual(snapshot(folder), before)


if __name__ == '__main__':
    unittest.main()
