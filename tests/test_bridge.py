import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
import urllib.error
import urllib.request
from maa.bridge import chat_request, server
from maa.store import Error


class Bridge(unittest.TestCase):
    def setUp(self):
        self.received = []
        parent = self
        class Native(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                parent.received.append(body)
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                chunks = [
                    {'choices': [{'delta': {'reasoning_content': 'planning'}}]},
                    {'choices': [{'delta': {'content': 'Hello '}}]},
                    {'choices': [{'delta': {'content': '世界'}}]},
                    {'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'call_test',
                     'function': {'name': 'apply_patch', 'arguments': '{"input":'}}]}}]},
                    {'choices': [{'delta': {'tool_calls': [{'index': 0,
                     'function': {'arguments': '"patch\\ntext"}'}}]}}]},
                    {'choices': [{'delta': {}, 'finish_reason': 'tool_calls'}],
                     'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}},
                ]
                for chunk in chunks:
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
        self.native = ThreadingHTTPServer(('127.0.0.1', 0), Native)
        self.adapter = server({'model': 'actual', 'upstream': f'http://127.0.0.1:{self.native.server_port}'}, port=0)
        for instance in (self.native, self.adapter):
            threading.Thread(target=instance.serve_forever, daemon=True).start()
    def tearDown(self):
        for instance in (self.adapter, self.native):
            instance.shutdown()
            instance.server_close()
    def request(self, stream):
        body = {'input': 'hello', 'stream': stream, 'reasoning': {'effort': 'ultra'},
                'tools': [{'type': 'custom', 'name': 'apply_patch'}]}
        req = urllib.request.Request(f'http://127.0.0.1:{self.adapter.server_port}/v1/responses',
                                     data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        return urllib.request.urlopen(req).read()

    def test_sse_order_text_reasoning_custom_tool_and_usage(self):
        wire = self.request(True).decode()
        events = [json.loads(line[6:]) for line in wire.splitlines() if line.startswith('data: ')]
        self.assertEqual([e['sequence_number'] for e in events], list(range(len(events))))
        self.assertEqual(events[-1]['type'], 'response.completed')
        output = events[-1]['response']['output']
        self.assertEqual(output[0]['summary'][0]['text'], 'planning')
        self.assertEqual(output[1]['content'][0]['text'], 'Hello 世界')
        self.assertEqual(output[2]['type'], 'custom_tool_call')
        self.assertEqual(output[2]['input'], 'patch\ntext')
        self.assertEqual(events[-1]['response']['usage']['total_tokens'], 15)
        self.assertEqual(self.received[0]['reasoning_effort'], 'ultra')

    def test_nonstreaming_has_identical_complete_items(self):
        result = json.loads(self.request(False))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['output'][2]['input'], 'patch\ntext')

    def test_tool_output_replay_preserves_call_identity_and_payload(self):
        body = {'input': [{'type': 'custom_tool_call', 'call_id': 'c1', 'name': 'apply_patch', 'input': 'patch'},
                          {'type': 'custom_tool_call_output', 'call_id': 'c1', 'output': 'applied'}]}
        chat, _ = chat_request(body, 'native')
        self.assertEqual(chat['messages'][0]['tool_calls'][0]['id'], 'c1')
        self.assertEqual(json.loads(chat['messages'][0]['tool_calls'][0]['function']['arguments']), {'input': 'patch'})
        self.assertEqual(chat['messages'][1], {'role': 'tool', 'tool_call_id': 'c1', 'content': 'applied'})

    def test_namespace_tools_and_replay_round_trip(self):
        from maa.bridge import Responses
        body = {'tools': [{'type': 'namespace', 'name': 'functions', 'tools': [
            {'type': 'function', 'name': 'exec_command', 'parameters': {'type': 'object'}}]}],
            'input': [{'type': 'function_call', 'namespace': 'functions', 'name': 'exec_command',
                       'call_id': 'c1', 'arguments': '{"cmd":"pwd"}'}]}
        chat, mapping = chat_request(body, 'native')
        name = chat['tools'][0]['function']['name']
        self.assertEqual(chat['messages'][0]['tool_calls'][0]['function']['name'], name)
        result = Responses('native', mapping, lambda event: None)
        result.delta({'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'c1',
                     'function': {'name': name, 'arguments': '{"cmd":"pwd"}'}}]}}]})
        item = result.finish()['output'][0]
        self.assertEqual(item['namespace'], 'functions')
        self.assertEqual(item['name'], 'exec_command')

    def test_unavailable_hosted_search_does_not_break_local_tools(self):
        chat, _ = chat_request({'tools': [{'type': 'web_search'},
                   {'type': 'function', 'name': 'mcp_search', 'parameters': {'type': 'object'}}]}, 'native')
        self.assertEqual([t['function']['name'] for t in chat['tools']], ['mcp_search'])
        with self.assertRaisesRegex(Error, 'built-in tool'):
            chat_request({'tools': [{'type': 'computer_use'}]}, 'native')
        with self.assertRaisesRegex(Error, 'stateless'):
            chat_request({'previous_response_id': 'old'}, 'native')


if __name__ == '__main__':
    unittest.main()
