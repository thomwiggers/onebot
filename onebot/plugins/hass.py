# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.psa` PSA
================================================

This plugin allows admins to send broadcasts
"""

from json import JSONDecodeError
from irc3 import plugin
from irc3.plugins.command import command

import requests


@plugin
class HassPlugin(object):
    """HomeAssistant Plugin"""

    requires = [
        "irc3.plugins.command",
    ]

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.config = bot.config.get(__name__, {})
        self.api_key = self.config.get("api_key")
        self.hass_host = self.config.get("hass_host")
        self.allowed_sensors = self.config.get("sensors")

    @command
    def solar(self, _mask, _target, _args):
        """Get the current yield of Thom's solar panels

        %%solar
        """
        return self.get_sensor("pv_yield_now")

    @command
    def sensor(self, _mask, _target, args) -> str:
        """Get the current value of a HASS sensor in Thom's home.

        Specify sensor_name without `sensor.`.

        %%sensor <sensor_name>
        """
        return self.get_sensor(args["<sensor_name>"])

    def get_sensor(self, sensor_name: str) -> str:
        if sensor_name not in self.allowed_sensors:
            return "Invalid sensor"
        url = f"{self.hass_host}/api/states/sensor.{sensor_name}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        rsp = requests.get(url, headers=headers)
        if not rsp.ok:
            self.log.error(
                "Invalid response from HA: code %d: '%r'", rsp.status_code, rsp.text
            )
            return "Invalid response from Home Assistant"

        try:
            data = rsp.json()
            self.log.debug("JSON from HA: %r", data)
        except JSONDecodeError:
            self.log.exception("Got invalid response from HA: %r", rsp.text)
            return "Invalid JSON from Home Assistant"

        try:
            state = data["state"]
            friendly_name = data["attributes"]["friendly_name"]
            unit = data["attributes"]["unit_of_measurement"]
        except KeyError:
            self.log.exception("Got weird response from HA: %r", rsp.text)
            return "JSON not as expected from Home Assistant"

        return f"{friendly_name}: {state} {unit}"
