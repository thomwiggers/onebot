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


class ExecutePlugin:
    """Execute commands after having connected"""

    __irc3_plugin__ = True

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        config = bot.config.get(__name__, {})
        self.commands = config.get('commands', [])

    def connection_made(self, **kwargs):
        for command in self.commands:
            self.bot.send(command)
