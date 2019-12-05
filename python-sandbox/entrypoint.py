#!/usr/bin/env python

import io
import multiprocessing

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
        success = False
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = compile(self.cmd, "<PEBKAC>", "single")
                success = True
            except (SyntaxError, OverflowError, ValueError) as e:
                print(e, file=sys.stderr)
            if success:
                try:
                    exec(code)
                except Exception as e:
                    print(repr(e), file=sys.stderr)
        out = out.getvalue().strip()
        if out:
            print(f"Stdout: {out!r}")
        err = err.getvalue().strip()
        if err:
            print(f"Stderr: {err!r}")


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

