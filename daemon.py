import os
import sys
import asyncio
import json
from utils import scan_json
import traceback
import time
import config

loop = asyncio.get_event_loop()
clients = {}
process_conn = None
log_time = 0
log_buffer = []

def response(conn, **res):
    if not conn: return
    conn.write(json.dumps(res).encode())

def send_log(client, **kwargs):
    if len(log_buffer) < 1: return
    if 'time' in kwargs:
        i = 0
        while i < len(log_buffer):
            if log_buffer[i]['time'] > kwargs['time']: break;
            i += 1
    else:
        i = len(log_buffer)-kwargs['count']
    response(client['conn'], status='ok', log=log_buffer[i:])
    client['log_last_push_time'] = log_buffer[-1]['time']

def push_logs():
    for (id, client) in clients.items():
        if not client['properties']['push_notifications']: continue
        if log_time > client['log_last_push_time']:
            send_log(client, time=client['log_last_push_time'])
            client['log_last_push_time'] = log_time
    loop.call_later(config.log_push_interval, push_logs);

def log(message, **kwargs):
    if 'level' in kwargs:
        message = '['+kwargs['level']+'] ' + message
    global log_time, log_buffer
    new_time = time.time()
    while new_time <= log_time:
        new_time += 0.001
    log_time = new_time
    sys.stdout.write(message)
    log_buffer.append({
        'time': log_time,
        'message': message
    })
    if len(log_buffer) > config.backlog:
        log_buffer.pop()

class ProcessProtocol(asyncio.SubprocessProtocol):
    def connection_made(self, transport):
        global process_conn
        process_conn = transport
        log("process started\n", level='console')

    def pipe_data_received(self, fd, data):
        log(data.decode())

    def process_exited(self):
        global process_conn
        process_conn = None
        log("process stopped\n", level='console')

def default_properties():
    return {
        'push_notifications': False,
    }

class APIException(Exception):
    pass

_id = 0
class ServerProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        global _id
        _id += 1
        self.client = {
            'id': _id,
            'conn': transport,
            'properties': default_properties(),
            'log_last_push_time': 0
        }
        clients[_id] = self.client
        self.buffer = b'';

    def connection_lost(self, exc):
        del clients[self.client['id']]

    def data_received(self, data):
        conn = self.client['conn']
        self.buffer += data
        while True:
            (req, been_read, error) = scan_json(self.buffer)
            self.buffer = self.buffer[been_read:]
            if error:
                response(conn, status="error", error=error)
                continue
            if not req: break

            try:
                method = req['method']
                if method not in method_dispatch_table:
                    response(conn, status="error", error="unknown method "+repr(method))
                    continue
                res = method_dispatch_table[method](self.client, req)
                if res: response(conn, **res)
            except APIException as e:
                response(conn, status="error", error=str(e))
            except Exception as e:
                trace = traceback.format_exc()
                print(trace)
                response(conn, status="error", error=trace)

def check_fields(req, *fields):
    for f in fields:
        if f not in req: raise APIException("missing parameter '"+f+"'")

def get_log(client, req):
    if ('time' not in req) and ('count' not in req): raise APIException("either 'time' or 'count' must be specified")
    if 'count' in req:
        send_log(client, count=req['count'])
        return
    send_log(client, time=req['time'])

def set_property(client, req):
    check_fields(req, 'key', 'value')
    client['properties'][req['key']] = req['value']
    return {'status': 'ok'}

def daemon_command(client, req):
    check_fields(req, 'command')
    cmd = req['command'].lower()
    if cmd == 'start':
        if process_conn: raise APIException("process already running")
        if not os.path.exists(config.process_working_directory): raise Exception("directory '"+config.process_working_directory+"' does not exist")
        if not os.path.isdir(config.process_working_directory): raise Exception("'"+config.process_working_directory+"' is not a directory")
        loop.create_task(
            loop.subprocess_exec(ProcessProtocol, *config.process_command_line, cwd=config.process_working_directory)
        )
        return {'status': 'ok'}
    raise APIException("unknown daemon command '"+cmd+"'")

def process_command(client, req):
    check_fields(req, 'command')
    cmd = req['command']
    if cmd[-1] != '\n': cmd += '\n'
    if not process_conn: raise APIException("process not running at the moment")
    process_conn.get_pipe_transport(0).write(cmd.encode())
    return {'status': 'ok'}

method_dispatch_table = {
    'get_log': get_log,
    'set_property': set_property,
    'daemon_command': daemon_command,
    'process_command': process_command,
}

try:
    os.remove(config.daemon_socket)
except FileNotFoundError:
    pass

socket_server = loop.run_until_complete(
    loop.create_unix_server(ServerProtocol, config.daemon_socket)
)
push_logs();
print("started")

try:
    loop.run_forever()
except KeyboardInterrupt:
    print("\nKeyboardInterrupt")
    pass

socket_server.close()
loop.run_until_complete(socket_server.wait_closed())
os.remove(config.daemon_socket)

loop.close()