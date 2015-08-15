"""
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
"""

import irc3


class ExecutePlugin:
    """Execute commands after having connected"""

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        config = bot.config.get(__name__, {})
        self.commands = config.get('commands', [])

    @irc3.event(irc3.rfc.CONNECTED)
    def connection_made(self, **kwargs):
        for command in self.commands:
            self.log.debug("Sending command %s", command)
            self.bot.send(command)
        if not self.commands:
            self.log.warning("No perform commands!")
