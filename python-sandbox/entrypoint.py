#!/usr/bin/env python

import io
import multiprocessing
import sys

from contextlib import redirect_stdout, redirect_stderr


TIMEOUT = 5


class UserProcess(multiprocessing.Process):
    """The user-provided process"""

    def __init__(self, cmd, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmd = cmd

    def run(self):
        """Compile and capture the output"""
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
