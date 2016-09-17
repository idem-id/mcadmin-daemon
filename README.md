### overview

simple daemon that executes a process and provides access to it's stdin and stdout via unix socket and simple json api.
it stores limited amount of log messages in a buffer, and either sends new messages to connected clients itself, or when explicitly requested.

### api

every response has property `"status"` which can be either `"ok"` or `"error"`.
on error, `"error"` property added with error message in it.

requests:

`{"method": "daemon_command", "command": "…"}` - send command to daemon. currently it understands single command, `start`, which tries to start a process.

`{"method": "process_command", "command": "…"}` - forwards anything in `"command"` to process' stdin.

`{"method": "get_log", ("time": … | "count": …)}` - retrieve process' last `"count"` logs, or everything newer than `"time"`.
<br>response: `{"status": "ok", "log": [{"time":…, "message":"…"}, …]}`

`{"method": "set_property", "key": "…", "value": "…"}` - set client's property.
<br>currently available properties:
<br>`push_notifications` - affects server initiated log forwarding. default is `False`.
<br>`keep_connection` - keep connection after sent response. default is `False`.

### example usage

* copy `config.py.example` to `config.py`, set proper working directory and command line.
* run `python3 daemon.py` and `python3 client.py` in separate terminal emulators.
* type `:start` in client.
* enjoy
* ctrl+c to stop them. (currenly daemon doesn't terminate child process gracefully)
