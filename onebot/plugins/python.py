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
        cmd = ' '.join(args['<command>'])
        self.log.debug("Command: '%s'", cmd)
        proc = subprocess.run(
            ["docker", "run", "--rm", "--net", "none",
             "--pids-limit", "5", "--memory", "100M",
             "--cpus", "1", "twiggers/python-sandbox", cmd],
            capture_output=True, text=True)
        if proc.returncode != 0:
            return "Error code {} when calling Docker".format(proc.returncode)
        lines = proc.stdout.split("\n")
        self.log.debug("Received: %s", proc.stdout)
        if len(lines) > 2:
            self.log.warning("Too many lines for '%s'", cmd)
            self.log.info("Output: %r", lines)
            return "Too many lines returned?"
        for line in lines:
            yield line[:200]

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
