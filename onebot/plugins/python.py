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


class PythonPlugin:
    """Execute commands after having connected"""

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)

    @command
    def py(self, mask, target, args):
        """Execute a command in a Python 3 interpreter

            %%py <command>...
        """
        cmd = ' '.join(args['<command>'])
        print("Command: ", cmd)
        proc = subprocess.run(
            ["docker", "run", "--rm", "--net", "none",
             "twiggers/python-sandbox", cmd],
            capture_output=True, text=True)
        if proc.returncode != 0:
            self.bot.privmsg(
                target,
                "Error code {} when calling Docker".format(proc.returncode))
        lines = proc.stdout.split("\n")
        assert len(lines) < 3, "Too many lines returned?"
        for line in lines:
            self.bot.privmsg(target, line)

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
