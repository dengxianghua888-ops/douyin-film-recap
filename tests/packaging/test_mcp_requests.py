"""Malformed clients must not terminate the newline-delimited MCP connection."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


SERVER = Path(__file__).resolve().parents[2] / 'scripts' / 'mcp_server.py'
INVALID_OBJECTS = (None, [], [1], '', 'invalid', False, True, 0, 1)


class McpRequestTests(unittest.TestCase):
    def exchange(self, messages):
        result = subprocess.run(
            [sys.executable, str(SERVER)],
            input=''.join(json.dumps(message) + '\n' for message in messages),
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_invalid_params_return_errors_and_connection_continues(self):
        messages = []
        for method in ('initialize', 'tools/call', 'ping', 'tools/list'):
            for params in INVALID_OBJECTS:
                identifier = len(messages) + 1
                messages.extend([
                    {'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params},
                    {'jsonrpc': '2.0', 'id': identifier + 1, 'method': 'ping'},
                ])
        responses = self.exchange(messages)
        self.assertEqual(len(responses), len(messages))
        for index, response in enumerate(responses):
            self.assertEqual(response['id'], messages[index]['id'])
            if index % 2 == 0:
                self.assertEqual(response['error']['code'], -32602)
                self.assertEqual(response['error']['message'], 'PARAMS_OBJECT_REQUIRED')
            else:
                self.assertEqual(response['result'], {})

    def test_invalid_arguments_are_not_coerced_to_empty_objects(self):
        messages = []
        for arguments in INVALID_OBJECTS:
            identifier = len(messages) + 1
            messages.extend([
                {'jsonrpc': '2.0', 'id': identifier, 'method': 'tools/call',
                 'params': {'name': 'list_skills', 'arguments': arguments}},
                {'jsonrpc': '2.0', 'id': identifier + 1, 'method': 'ping'},
            ])
        responses = self.exchange(messages)
        self.assertEqual(len(responses), len(messages))
        for index, response in enumerate(responses):
            self.assertEqual(response['id'], messages[index]['id'])
            if index % 2 == 0:
                self.assertEqual(response['error']['code'], -32602)
                self.assertEqual(response['error']['message'], 'TOOL_ARGUMENTS_OBJECT_REQUIRED')
            else:
                self.assertEqual(response['result'], {})

    def test_omitted_and_object_arguments_and_initialize_remain_supported(self):
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'initialize',
             'params': {'protocolVersion': '2025-06-18'}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
             'params': {'name': 'list_skills'}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
             'params': {'name': 'list_skills', 'arguments': {}}},
        ]
        responses = self.exchange(messages)
        self.assertEqual(len(responses), 4)
        self.assertEqual(responses[0]['result']['protocolVersion'], '2025-03-26')
        self.assertEqual(responses[1]['result']['protocolVersion'], '2025-06-18')
        for response in responses[2:]:
            self.assertFalse(response['result']['isError'])
            content = json.loads(response['result']['content'][0]['text'])
            self.assertTrue(content['entries'])

    def test_malformed_notifications_are_silent_and_connection_continues(self):
        responses = self.exchange([
            {'jsonrpc': '2.0', 'method': 'initialize', 'params': None},
            {'jsonrpc': '2.0', 'method': 'tools/call', 'params': [1]},
            {'jsonrpc': '2.0', 'method': 'tools/call',
             'params': {'name': 'list_skills', 'arguments': False}},
            {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
        ])
        self.assertEqual(responses, [{'jsonrpc': '2.0', 'id': 1, 'result': {}}])


if __name__ == '__main__':
    unittest.main()
