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
import subprocess


@irc3.plugin
class PythonPlugin:
    """Execute commands after having connected"""

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)

    @command(use_shlex=False)
    def py(self, _mask, _target, args):
        """Execute a command in a Python 3 interpreter

        %%py <command>...
        """
        cmd = " ".join(args["<command>"])
        self.log.debug("Command: '%s'", cmd)
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--read-only",
                "--security-opt=no-new-privileges:true",
                "--net=none",
                "--log-driver=none",
                "--cap-drop=ALL",
                "--pids-limit=10",
                "--memory=50M",
                "--cpus=0.5",  # CPU shares
                "--ipc=none",  # inter-process communication (none < priv)
                "twiggers/python-sandbox",
                cmd,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0:
            self.log.warning("Error when calling docker: '%s'", proc.stderr)
            yield "Error code {} when calling Docker".format(proc.returncode)
            return
        lines = proc.stdout.split("\n")
        self.log.debug("Received: %s", proc.stdout)
        if len(lines) > 2:
            self.log.warning("Too many lines for '%s'", cmd)
            self.log.info("Output: %r", lines)
            yield "Too many lines returned?"
            return
        for line in lines:
            yield line[:200]

    @classmethod
    def reload(cls, old: Self) -> Self:  # pragma: no cover
        return cls(old.bot)
