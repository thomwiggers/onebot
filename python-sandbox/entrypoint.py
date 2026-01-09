#!/usr/bin/env python

import io
import multiprocessing
import resource
import sys

from contextlib import redirect_stdout, redirect_stderr


TIMEOUT = 5


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
    # Note: This might prevent some imports or complex operations,
    # but it's great for simple snippets.
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except Exception:
        pass
    # Limit file size creation
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


class UserProcess(multiprocessing.Process):
    """The user-provided process"""

    def __init__(self, cmd, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmd = cmd

    def run(self):
        """Compile and capture the output"""
        set_resource_limits()
        out = io.StringIO()
        err = io.StringIO()

        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = compile(self.cmd, "<PEBKAC>", "single")
                try:
                    exec(code, {}, {})
                except Exception as e:
                    print(e, file=sys.stderr)
            except (SyntaxError, OverflowError, ValueError) as e:
                print(e, file=sys.stderr)

        out = out.getvalue().strip()
        if out:
            print(f"Stdout: {out!r}")
        err = err.getvalue().strip()
        if err:
            print(f"Stderr: {err!r}")
        if not (out or err):
            print("No output.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <cmdline>", file=sys.stderr)
        sys.exit(1)
    process = UserProcess(sys.argv[1])
    process.start()
    process.join(TIMEOUT)
    if process.is_alive():
        process.terminate()
        print(f"Terminated after {TIMEOUT} seconds.")
