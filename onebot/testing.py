import asyncio

import irc3
from irc3.testing import BotTestCase as Irc3BotTestCase, call_later, call_soon
from unittest.mock import create_autospec, MagicMock, patch

__all__ = ["BotTestCase", "IrcBot", "patch"]
__unittest = True


class IrcBot(irc3.IrcBot):
    """Testing IrcBot that properly manages event loops.

    Differences from irc3.testing.IrcBot:
    - Closes the temporary event loop created for autospec (irc3 leaks it)
    - check_required() is a no-op (avoids creating ~/.irc3/ during tests)
    - Defaults asynchronous=False when a real loop is provided, preventing
      irc3 from spawning a process_queue coroutine that is never cleaned up
    """

    def __init__(self, **config):
        if "loop" not in config:
            # irc3.testing.IrcBot creates a real event loop just to autospec
            # it, then discards the real loop without closing it. We close it.
            temp_loop = asyncio.new_event_loop()
            loop = create_autospec(temp_loop, spec_set=True)
            temp_loop.close()
            loop.call_later = call_later
            loop.call_soon = call_soon
            loop.time.return_value = 10
            config.update(testing=True, asynchronous=False, level=1000, loop=loop)
        else:
            config.setdefault("asynchronous", False)
            config.update(testing=True, level=1000)
        super().__init__(**config)
        self.protocol = irc3.IrcConnection()
        self.protocol.closed = False
        self.protocol.factory = self
        self.protocol.transport = MagicMock()
        self.protocol.write = MagicMock()

    def check_required(self):
        pass

    @property
    def sent(self):
        values = [tuple(c)[0][0] for c in self.protocol.write.call_args_list]
        self.protocol.write.reset_mock()
        return values


class BotTestCase(Irc3BotTestCase):
    """Extends irc3's BotTestCase with proper event loop cleanup.

    Differences from irc3.testing.BotTestCase:
    - Uses our IrcBot instead of irc3.testing.IrcBot (avoids leaked event loops)
    - Registers addCleanup handler that cancels pending asyncio tasks and
      closes real event loops after each test, preventing ResourceWarnings
    """

    def callFTU(self, **config):
        config = dict(self.config, **config)
        self.bot = IrcBot(**config)
        # Register cleanup for real event loops to prevent ResourceWarnings
        loop = self.bot.loop
        if isinstance(loop, asyncio.AbstractEventLoop):
            self.addCleanup(self._cleanup_loop, loop)
        return self.bot

    @staticmethod
    def _cleanup_loop(loop):
        """Cancel pending tasks and close the event loop."""
        if loop.is_closed():
            return
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except Exception:
            pass
        finally:
            loop.close()
