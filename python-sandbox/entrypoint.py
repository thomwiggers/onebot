#!/usr/bin/env python

import io
import json
import multiprocessing
import resource
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from contextlib import redirect_stdout, redirect_stderr

TIMEOUT = 5
LISTEN_PORT = 8080


def set_resource_limits():
    """Set resource limits for the user process"""
    # Limit memory to 100MB
    mem_limit = 100 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    # Limit CPU time to TIMEOUT + 1 seconds
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT + 1, TIMEOUT + 1))
    # Disable core dumps
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Limit number of processes to 0 (can't fork)
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except Exception:
        pass
    # Limit file size creation
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


def run_user_code(cmd, queue):
    """Compile and capture the output in a subprocess"""
    set_resource_limits()
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = compile(cmd, "<PEBKAC>", "single")
            try:
                exec(code, {}, {})
            except Exception as e:
                print(e, file=sys.stderr)
        except (SyntaxError, OverflowError, ValueError) as e:
            print(e, file=sys.stderr)

    queue.put({"stdout": out.getvalue().strip(), "stderr": err.getvalue().strip()})


class SandboxHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data)
            code = data.get("code", "")
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=run_user_code, args=(code, queue))
        process.start()
        process.join(TIMEOUT)

        if process.is_alive():
            process.terminate()
            response = {"stdout": "", "stderr": f"Terminated after {TIMEOUT} seconds."}
        else:
            if not queue.empty():
                response = queue.get()
            else:
                response = {"stdout": "", "stderr": "No output received from process."}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        # Silence standard logging to keep container logs clean
        return


def run_server():
    server_address = ("", LISTEN_PORT)
    httpd = HTTPServer(server_address, SandboxHandler)
    print(f"Starting sandbox server on port {LISTEN_PORT}...")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
