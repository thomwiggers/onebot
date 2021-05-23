from irc3.testing import BotTestCase as Irc3BotTestCase, IrcBot as Irc3IrcBot

from unittest.mock import patch

__unittest = True


class IrcBot(Irc3IrcBot):
    def check_required(self):
        pass


class BotTestCase(Irc3BotTestCase):
    def callFTU(self, *args, **kwargs):
        with patch("irc3.testing.IrcBot.check_required") as p:
            super().callFTU(*args, **kwargs)
            p.assert_called()
