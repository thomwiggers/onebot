# -*- coding: utf-8 -*-
"""
================================================
:mod:`onebot.plugins.grip` GRIP Boulderhal
================================================

This plugin allows to query the availability at GRIP Nijmegen
"""

from datetime import date

from irc3 import plugin
from irc3.plugins.command import command

import requests
import dateparser

import logging

logger = logging.getLogger(__name__)


GRIP_URL: str = (
    "https://gripnijmegen.dewi-online.nl/iframe/"
    "reservations/156/opening-hours/1570/1015016"
)


def parse_date(datestr: str) -> date:
    datum = dateparser.parse(
        datestr, languages=["en", "nl"], settings={"PREFER_DATES_FROM": "future"}
    )
    if datum:
        return datum.date()
    raise ValueError("Invalid date")


def grip_availability(day: date):
    """Get the availability for date"""
    response = requests.get(
        GRIP_URL,
        params={
            "date": day.isoformat(),
            "areas": [803],
            "show_all": 0,
        },
    )
    try:
        data = response.json()
        max_left = data["max_left"]
        slots = []
        for block in data["blocks"]:
            slot = {}
            slot["start"] = block["start"]
            slot["end"] = block["end"]
            if block["status"] == "free":
                slot["status"] = "quiet"
            elif block["status"] == "partial":
                slot["status"] = "busy"
            else:
                slot["status"] = block["status"]
            slots.append(slot)
        return (slots, max_left)
    except ValueError:
        logger.exception("Failed to decode response")
    except KeyError:
        logger.exception("No blocks in data?")
    return (None, 0)


@plugin
class GRIPPlugin(object):
    """GRIP Plugin"""

    requires = [
        "irc3.plugins.command",
    ]

    def __init__(self, bot):
        self.bot = bot

    @command
    def grip(self, _mask, _target, args):
        """Check the availability at GRIP

        %%grip [<day>...]
        """
        days = args["<day>"] or ["today"]

        for day in days:
            try:
                day_date = parse_date(day)
            except ValueError as exc:
                yield f"Didn't understand {day}: {exc}"
                continue
            (slots, max_left) = grip_availability(day_date)
            if slots is None or all(slot["status"] == "full" for slot in slots):
                yield f"{day}: no slots free"
                continue
            response = []
            for slot in slots:
                if slot["status"] == "full":
                    continue
                response.append(f"{slot['start']}—{slot['end']}: {slot['status']}")

            yield f"{day} (max spots free: {max_left}): {'; '.join(response)}."
