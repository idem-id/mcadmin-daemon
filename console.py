import sys
import asyncio
import json
from utils import scan_json
import config

loop = asyncio.get_event_loop()

conn = None
log_last = 0

def request(**req):
    if not conn: return
    conn.write(json.dumps(req).encode())

class ClientProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        global conn
        conn = transport
        request(method="get_log", count=10)
        request(method="set_property", key="push_notifications", value=True)
        self.buffer = b'';
        print("connected")

    def connection_lost(self, exc):
        loop.stop()
        print("disconnected")

    def data_received(self, data):
        self.buffer += data
        while True:
            (res, been_read, error) = scan_json(self.buffer)
            if error:
                print(error)
            self.buffer = self.buffer[been_read:]
            if not res: break
            if res['status'] == 'ok':
                if 'log' in res:
                    global log_last
                    for ent in res['log']:
                        sys.stdout.write(ent['message'])
                        if ent['time'] > log_last: log_last = ent['time']
            else:
                print("error: "+res['error'])

def keyboard_reader():
    line = sys.stdin.readline().strip()
    if conn:
        if line == ':log':
            request(method="get_log", time=log_last)
            return
        if line[0] == ':':
            request(method="daemon_command", command=line[1:])
        else:
            request(method="process_command", command=line)

loop.add_reader(sys.stdin, keyboard_reader)
try:
    loop.run_until_complete(
        loop.create_unix_connection(ClientProtocol, config.daemon_socket)
    );
except FileNotFoundError:
    print(config.daemon_socket+" doesn't exist")
    exit()

try:
    loop.run_forever()
except KeyboardInterrupt:
    print("\nKeyboardInterrupt")
    pass

loop.close()