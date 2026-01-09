"""
=====================================================
:mod:`onebot.plugins.python` Run python commands in docker
=====================================================

Allow to run Python commands

Config:
=======

.. code-block: ini

    [bot]
    includes=
      onebot.plugins.python
"""

from typing import Self
import irc3
from irc3.plugins.command import command
import requests
import os


@irc3.plugin
class PythonPlugin:
    """Execute commands after having connected"""

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.sandbox_url = os.environ.get("PYTHON_SANDBOX_URL", "http://localhost:8080")

    @command(use_shlex=False)
    def py(self, _mask, _target, args):
        """Execute a command in a Python 3 interpreter

        %%py <command>...
        """
        cmd = " ".join(args["<command>"])
        self.log.debug("Command: '%s'", cmd)
        try:
            response = requests.post(
                self.sandbox_url,
                json={"code": cmd},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            stdout = data.get("stdout", "")
            stderr = data.get("stderr", "")

            if stderr:
                yield f"Error: {stderr[:200]}"
                return

            if not stdout:
                yield "No output."
                return

            lines = stdout.split("\n")
            if len(lines) > 2:
                self.log.warning("Too many lines for '%s'", cmd)
                self.log.info("Output: %r", lines)
                yield "Too many lines returned?"
                return

            for line in lines:
                yield line[:200]

        except requests.exceptions.RequestException as e:
            self.log.error("Failed to connect to sandbox: %s", e)
            yield "Error: Could not connect to Python sandbox."

    @classmethod
    def reload(cls, old: Self) -> Self:  # pragma: no cover
        return cls(old.bot)
