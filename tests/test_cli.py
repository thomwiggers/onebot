import unittest
from unittest.mock import patch, MagicMock
from onebot import run


class TestCLI(unittest.TestCase):
    @patch("irc3.utils.parse_config")
    @patch("onebot.OneBot.from_config")
    @patch("onebot.OneBot.run")
    def test_run_basic(self, mock_run, mock_from_config, mock_parse_config):
        mock_parse_config.return_value = {}
        mock_bot = MagicMock()
        mock_from_config.return_value = mock_bot

        run(["config.ini"])

        mock_parse_config.assert_called_with("bot", "config.ini")
        mock_from_config.assert_called_with({"verbose": False, "debug": False})
        mock_bot.run.assert_called_once()

    @patch("irc3.utils.parse_config")
    @patch("onebot.OneBot.from_config")
    @patch("onebot.OneBot.run")
    def test_run_verbose_debug(self, mock_run, mock_from_config, mock_parse_config):
        mock_parse_config.return_value = {}
        mock_bot = MagicMock()
        mock_from_config.return_value = mock_bot

        run(["--verbose", "-d", "config.ini"])

        mock_parse_config.assert_called_with("bot", "config.ini")
        mock_from_config.assert_called_with({"verbose": True, "debug": True})

    @patch("irc3.utils.parse_config")
    @patch("onebot.OneBot.from_config")
    @patch("onebot.OneBot.run")
    @patch("onebot.OneBot.logging_config")
    @patch("irc3.config.get_file_config")
    @patch("os.path.expanduser")
    def test_run_logdir(
        self,
        mock_expanduser,
        mock_get_file_config,
        mock_run,
        mock_logging_config,
        mock_from_config,
        mock_parse_config,
    ):
        mock_parse_config.return_value = {}
        mock_bot = MagicMock()
        mock_from_config.return_value = mock_bot
        mock_expanduser.side_effect = lambda x: x

        run(["--logdir", "/tmp/logs", "config.ini"])

        mock_get_file_config.assert_called_with("/tmp/logs")

    @patch("irc3.utils.parse_config")
    @patch("onebot.OneBot.from_config")
    @patch("onebot.OneBot.run")
    def test_run_multiple_configs(self, mock_run, mock_from_config, mock_parse_config):
        mock_parse_config.return_value = {}
        mock_bot = MagicMock()
        mock_from_config.return_value = mock_bot

        run(["config1.ini", "config2.ini"])

        mock_parse_config.assert_called_with("bot", "config1.ini", "config2.ini")


if __name__ == "__main__":
    unittest.main()
