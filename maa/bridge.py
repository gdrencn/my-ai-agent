"""Local stateless Responses adapter over native chat completions.

Keeps function/custom tool history and SSE ordering compatible with Codex. It
does not implement hosted search or pretend unsupported built-in tools exist.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
import urllib.error
import urllib.request
import uuid
import hashlib
from .store import Error


def text_content(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return json.dumps(content, ensure_ascii=False)
    parts = []
    for part in content:
        kind = part.get('type')
        if kind in ('input_text', 'output_text', 'text'):
            parts.append({'type': 'text', 'text': part['text']})
        elif kind == 'input_image':
            parts.append({'type': 'image_url', 'image_url': {'url': part['image_url']}})
        else:
            raise Error(f'Unsupported local input content: {kind}')
    return parts


def tool_name(name, namespace=None):
    qualified = (namespace + '__' if namespace else '') + name
    if len(qualified) > 64:
        qualified = qualified[:39] + '_' + hashlib.sha256(qualified.encode()).hexdigest()[:24]
    return qualified


def chat_request(body, model):
    messages, custom = [], {}
    if body.get('previous_response_id') or body.get('conversation'):
        raise Error('Local API is stateless; replay the full conversation input')
    if body.get('instructions'):
        messages.append({'role': 'system', 'content': body['instructions']})
    items = body.get('input', [])
    if isinstance(items, str):
        items = [{'role': 'user', 'content': items}]
    tools = []
    def add_tool(tool, namespace=None):
        kind = tool.get('type')
        if kind in ('web_search', 'web_search_preview'):
            # Codex advertises hosted search by default. Neither native chat
            # endpoint implements OpenAI-hosted search; omit that unavailable
            # capability, without writing/overriding the user's web_search key.
            # Separately configured MCP search is a normal function and survives.
            return
        if kind == 'namespace':
            for child in tool.get('tools', []):
                add_tool(child, tool['name'])
            return
        native_name = tool_name(tool.get('name', ''), namespace)
        if kind == 'function':
            fn = {k: tool[k] for k in ('name', 'description', 'parameters', 'strict') if k in tool}
            fn['name'] = native_name
            tools.append({'type': 'function', 'function': fn})
        elif kind == 'custom':
            tools.append({'type': 'function', 'function': {'name': native_name,
                          'description': tool.get('description', ''),
                          'parameters': {'type': 'object', 'properties': {'input': {'type': 'string'}},
                                         'required': ['input'], 'additionalProperties': False}}})
        else:
            raise Error(f'Local backend does not provide built-in tool {kind}; configure a separate tool integration')
        if native_name in custom:
            raise Error('Duplicate local tool name: ' + native_name)
        custom[native_name] = {'name': tool['name'], 'namespace': namespace, 'custom': kind == 'custom'}
    for tool in body.get('tools', []):
        add_tool(tool)
    for item in items:
        kind = item.get('type', 'message')
        if kind == 'message':
            role = item.get('role', 'user')
            messages.append({'role': 'system' if role == 'developer' else role,
                             'content': text_content(item.get('content', ''))})
        elif kind in ('function_call', 'custom_tool_call'):
            arguments = item.get('arguments', '{}') if kind == 'function_call' else json.dumps({'input': item.get('input', '')})
            call = {'id': item['call_id'], 'type': 'function',
                    'function': {'name': tool_name(item['name'], item.get('namespace')), 'arguments': arguments}}
            if messages and messages[-1].get('role') == 'assistant' and 'tool_calls' in messages[-1]:
                messages[-1]['tool_calls'].append(call)
            else:
                messages.append({'role': 'assistant', 'content': None, 'tool_calls': [call]})
        elif kind in ('function_call_output', 'custom_tool_call_output'):
            output = item.get('output', '')
            messages.append({'role': 'tool', 'tool_call_id': item['call_id'],
                             'content': output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)})
        elif kind == 'reasoning':
            # Encrypted OpenAI reasoning has no local meaning. Visible summaries
            # remain in history without inventing hidden chain-of-thought.
            visible = '\n'.join(p.get('text', '') for p in item.get('summary', []))
            if visible:
                messages.append({'role': 'assistant', 'content': visible})
        else:
            raise Error(f'Unsupported local Responses input item: {kind}')
    request = {'model': model, 'messages': messages, 'stream': True,
               'stream_options': {'include_usage': True}}
    if tools:
        request['tools'] = tools
    for key in ('temperature', 'top_p', 'parallel_tool_calls'):
        if key in body:
            request[key] = body[key]
    if 'max_output_tokens' in body:
        request['max_tokens'] = body['max_output_tokens']
    if body.get('reasoning', {}).get('effort') is not None:
        request['reasoning_effort'] = body['reasoning']['effort']
    choice = body.get('tool_choice')
    if isinstance(choice, dict) and choice.get('type') in ('function', 'custom'):
        request['tool_choice'] = {'type': 'function', 'function': {'name': tool_name(choice['name'], choice.get('namespace'))}}
    elif choice is not None:
        request['tool_choice'] = choice
    return request, custom


class Responses:
    def __init__(self, model, custom, emit):
        self.custom, self.emit, self.sequence = custom, emit, 0
        self.value = {'id': 'resp_' + uuid.uuid4().hex, 'object': 'response',
                      'created_at': int(time.time()), 'model': model, 'status': 'in_progress',
                      'output': [], 'error': None, 'usage': None}
        self.calls, self.message, self.reasoning = {}, None, None
        self.event('response.created', response=self.value.copy())
        self.event('response.in_progress', response=self.value.copy())

    def event(self, kind, **payload):
        self.emit({'type': kind, 'sequence_number': self.sequence, **payload})
        self.sequence += 1

    def add(self, item):
        index = len(self.value['output'])
        self.value['output'].append(item)
        self.event('response.output_item.added', output_index=index, item=dict(item))
        return index, item

    def delta(self, value):
        if value.get('usage'):
            usage = value['usage']
            self.value['usage'] = {'input_tokens': usage.get('prompt_tokens', 0),
                                   'output_tokens': usage.get('completion_tokens', 0),
                                   'total_tokens': usage.get('total_tokens', 0)}
        for choice in value.get('choices', []):
            delta = choice.get('delta') or choice.get('message') or {}
            reason = delta.get('reasoning_content') or delta.get('reasoning')
            if isinstance(reason, str) and reason:
                if self.reasoning is None:
                    self.reasoning = self.add({'id': 'rs_' + uuid.uuid4().hex, 'type': 'reasoning',
                                               'summary': [{'type': 'summary_text', 'text': ''}]})
                    i, item = self.reasoning
                    self.event('response.reasoning_summary_part.added', item_id=item['id'],
                               output_index=i, summary_index=0, part=dict(item['summary'][0]))
                i, item = self.reasoning
                item['summary'][0]['text'] += reason
                self.event('response.reasoning_summary_text.delta', item_id=item['id'], output_index=i,
                           summary_index=0, delta=reason)
            content = delta.get('content')
            if content:
                if self.message is None:
                    self.message = self.add({'id': 'msg_' + uuid.uuid4().hex, 'type': 'message',
                                             'role': 'assistant', 'status': 'in_progress',
                                             'content': [{'type': 'output_text', 'text': '', 'annotations': []}]})
                    i, item = self.message
                    self.event('response.content_part.added', item_id=item['id'], output_index=i,
                               content_index=0, part=dict(item['content'][0]))
                i, item = self.message
                item['content'][0]['text'] += content
                self.event('response.output_text.delta', item_id=item['id'], output_index=i,
                           content_index=0, delta=content)
            for call in delta.get('tool_calls', []):
                index = call.get('index', 0)
                fn = call.get('function', {})
                if index not in self.calls:
                    self.calls[index] = {'id': call.get('id') or 'call_' + uuid.uuid4().hex,
                                         'name': '', 'arguments': ''}
                row = self.calls[index]
                if call.get('id'):
                    row['id'] = call['id']
                row['name'] += fn.get('name', '')
                row['arguments'] += fn.get('arguments', '')
                # Emit at completion: native streams can fragment function names
                # and custom input JSON; do not expose invalid interim names.

    def finish(self):
        for row in self.calls.values():
            spec = self.custom.get(row['name'])
            if spec is None:
                raise Error('Model called an undeclared tool: ' + row['name'])
            if spec['custom']:
                try:
                    decoded = json.loads(row['arguments'])
                    content = decoded['input']
                    if not isinstance(content, str):
                        raise ValueError('custom input must be a string')
                except (ValueError, KeyError, TypeError) as exc:
                    raise Error(f'Model returned invalid custom-tool input: {row["name"]}: {exc}') from exc
                i, item = self.add({'id': 'ct_' + uuid.uuid4().hex, 'type': 'custom_tool_call',
                                    'call_id': row['id'], 'name': spec['name'], 'input': '', 'status': 'in_progress',
                                    **({'namespace': spec['namespace']} if spec['namespace'] else {})})
                self.event('response.custom_tool_call_input.delta', item_id=item['id'], output_index=i, delta=content)
                item['input'] = content
                self.event('response.custom_tool_call_input.done', item_id=item['id'], output_index=i, input=content)
            else:
                i, item = self.add({'id': 'fc_' + uuid.uuid4().hex, 'type': 'function_call',
                                    'call_id': row['id'], 'name': spec['name'], 'arguments': '', 'status': 'in_progress',
                                    **({'namespace': spec['namespace']} if spec['namespace'] else {})})
                self.event('response.function_call_arguments.delta', item_id=item['id'], output_index=i, delta=row['arguments'])
                item['arguments'] = row['arguments']
                self.event('response.function_call_arguments.done', item_id=item['id'], output_index=i,
                           arguments=row['arguments'])
        for i, item in enumerate(self.value['output']):
            if item['type'] == 'message':
                self.event('response.output_text.done', item_id=item['id'], output_index=i, content_index=0,
                           text=item['content'][0]['text'])
                self.event('response.content_part.done', item_id=item['id'], output_index=i, content_index=0,
                           part=item['content'][0])
            elif item['type'] == 'reasoning':
                self.event('response.reasoning_summary_text.done', item_id=item['id'], output_index=i,
                           summary_index=0, text=item['summary'][0]['text'])
                self.event('response.reasoning_summary_part.done', item_id=item['id'], output_index=i,
                           summary_index=0, part=item['summary'][0])
            item['status'] = 'completed'
            self.event('response.output_item.done', output_index=i, item=item)
        self.value['status'] = 'completed'
        self.event('response.completed', response=self.value)
        return self.value


def server(runtime, port=18443):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ('/health', '/v1/models'):
                self.send_json(200, {'status': 'ok'} if self.path == '/health' else
                               {'object': 'list', 'data': [{'id': runtime['model'], 'object': 'model'}]})
            else:
                self.send_json(404, {'error': {'message': 'Unknown local endpoint'}})

        def do_POST(self):
            started = False
            try:
                if self.path != '/v1/responses':
                    self.send_json(404, {'error': {'message': 'Only /v1/responses is supported'}})
                    return
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 32 * 1024 * 1024:
                    raise Error('Invalid local request size (limit 32 MiB)')
                body = json.loads(self.rfile.read(length))
                chat, custom = chat_request(body, runtime['model'])
                req = urllib.request.Request(runtime['upstream'] + '/v1/chat/completions',
                                             data=json.dumps(chat).encode(), headers={'Content-Type': 'application/json'})
                upstream = urllib.request.urlopen(req, timeout=600)
                streaming = body.get('stream', False)
                if streaming:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    started = True

                def emit(event):
                    if streaming:
                        wire = f'event: {event["type"]}\ndata: {json.dumps(event)}\n\n'
                        self.wfile.write(wire.encode())
                        self.wfile.flush()

                result = Responses(runtime['model'], custom, emit)
                with upstream:
                    content_type = upstream.headers.get('Content-Type', '')
                    if 'text/event-stream' not in content_type:
                        result.delta(json.load(upstream))
                    else:
                        done = False
                        for line in upstream:
                            if not line.startswith(b'data:'):
                                continue
                            data = line[5:].strip()
                            if data == b'[DONE]':
                                done = True
                                break
                            chunk = json.loads(data)
                            if chunk.get('error'):
                                raise Error(str(chunk['error']))
                            result.delta(chunk)
                            if any(c.get('finish_reason') for c in chunk.get('choices', [])):
                                done = True
                        if not done:
                            raise Error('Native stream closed without a completion marker')
                response = result.finish()
                if not streaming:
                    self.send_json(200, response)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:
                if isinstance(exc, urllib.error.HTTPError):
                    detail = exc.read(8192).decode(errors='replace')
                    message = f'Native HTTP {exc.code}: {detail}'
                else:
                    message = str(exc)
                if started:
                    event = {'type': 'error', 'code': 'local_backend_error', 'message': message}
                    try:
                        self.wfile.write(('event: error\ndata: ' + json.dumps(event) + '\n\n').encode())
                    except OSError:
                        pass
                else:
                    self.send_json(400, {'error': {'type': 'local_backend_error', 'message': message}})
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
