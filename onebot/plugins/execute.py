"""
=====================================================
:mod:`onebot.plugins.execute` Run commands on connect
=====================================================

Run commands on connect

Config:
=======

.. code-block: ini

    [bot]
    includes=
      onebot.plugins.execute
    [onebot.plugins.execute]
    commands=
      NS IDENTIFY f00bar
      PRIVMSG SomeBot :LetMeIn


irc3 also has a plugin now, might be more useful.
"""

import irc3
import time


class ExecutePlugin:
    """Execute commands after having connected"""

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        config = bot.config.get(__name__, {})
        self.commands = config.get('commands', [])
        self.delayed_commands = config.get('delayed_commands', [])

    @irc3.event(irc3.rfc.CONNECTED)
    def connected(self, **kwargs):
        self.log.info("Sending perform commands")
        for command in self.commands:
            self.log.debug("Sending command %s", command)
            self.bot.send(command)
        if not self.commands:  # pragma: no cover
            self.log.warning("No perform commands!")

        self.log.debug("Waiting for delayed commands")
        time.sleep(4)
        self.log.info("Sending delayed commands")
        for command in self.delayed_commands:
            self.log.debug("Sending command %s", command)
            self.bot.send(command)

    @classmethod
    def reload(cls, old):  # pragma: no cover
        return cls(old.bot)
