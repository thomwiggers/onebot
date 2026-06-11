import re
import logging
from typing import Self

import irc3
import requests
from irc3.plugins.command import command

logger = logging.getLogger(__name__)

RDW_BASE = "https://opendata.rdw.nl/resource/"
VEHICLE_DATASET = "m9d7-ebf2"
FUEL_DATASET = "8ys7-d773"


def normalize_plate(plate: str) -> str:
    """Strip dashes/spaces and uppercase a license plate.

    >>> normalize_plate("N-524-KT")
    'N524KT'
    >>> normalize_plate("n 524 kt")
    'N524KT'
    """
    return re.sub(r"[\s-]", "", plate).upper()


def format_date(yyyymmdd: str) -> str:
    """Reformat YYYYMMDD to DD-MM-YYYY.

    >>> format_date("20270806")
    '06-08-2027'
    """
    return f"{yyyymmdd[6:8]}-{yyyymmdd[4:6]}-{yyyymmdd[0:4]}"


def format_price(price_str: str) -> str:
    """Format price with Dutch thousands separator and euro sign.

    >>> format_price("27645")
    '€27.645'
    """
    return "€" + f"{int(price_str):,}".replace(",", ".")


def format_drivetrain(vehicle: dict, fuel: dict | None) -> str:
    """Format drivetrain: fuel type, engine size, power, emission level.

    >>> format_drivetrain({"cilinderinhoud": "998"}, {"brandstof_omschrijving": "Benzine", "nettomaximumvermogen": "88.30", "uitlaatemissieniveau": "EURO 6 AP"})
    'Benzine 1.0L 88kW EURO 6 AP'
    >>> format_drivetrain({"cilinderinhoud": "998"}, None)
    '1.0L'
    """
    parts = []
    if fuel:
        parts.append(fuel["brandstof_omschrijving"])
    parts.append(f"{int(vehicle['cilinderinhoud']) / 1000:.1f}L")
    if fuel:
        if fuel.get("nettomaximumvermogen"):
            parts.append(f"{int(float(fuel['nettomaximumvermogen']) + 0.5)}kW")
        if fuel.get("uitlaatemissieniveau"):
            parts.append(fuel["uitlaatemissieniveau"])
    return " ".join(parts)


def format_summary(plate: str, vehicle: dict, fuel: dict | None) -> str:
    """Format a one-line vehicle summary for IRC."""
    year = vehicle["datum_eerste_toelating"][:4]
    drivetrain = format_drivetrain(vehicle, fuel)
    apk = format_date(vehicle["vervaldatum_apk"])
    price = format_price(vehicle["catalogusprijs"])
    speed = vehicle.get("maximale_constructiesnelheid", "")
    title = (
        f"{vehicle['merk']} {vehicle['handelsbenaming']} "
        f"{vehicle['inrichting'].capitalize()}"
    )
    parts = [
        f"{plate}: {title}",
        year,
        drivetrain,
        f"Catalogus: {price}",
        f"APK: {apk}",
    ]
    if speed:
        parts.append(f"Top: {speed} km/h")
    return " | ".join(parts)


def _rdw_get(url: str, params: dict, app_token: str) -> list:
    headers = {"X-App-Token": app_token}
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


@irc3.plugin
class RdwKentekenPlugin:
    """Plugin for looking up Dutch vehicle registration data."""

    requires = ["irc3.plugins.command"]

    def __init__(self, bot):
        self.bot = bot
        self.log = bot.log.getChild(__name__)
        self.config = bot.config.get(__name__, {})
        self.app_token = self.config["rdw_app_token"]

    @command
    def rdw(self, mask, target, args):
        """Look up vehicle info by Dutch license plate.

        %%rdw <plate>
        """
        plate = normalize_plate(args["<plate>"])

        vehicles = _rdw_get(
            f"{RDW_BASE}{VEHICLE_DATASET}.json",
            {"kenteken": plate},
            self.app_token,
        )

        if not vehicles:
            self.bot.privmsg(target, "Kenteken niet gevonden.")
            return

        vehicle = vehicles[0]

        try:
            fuels = _rdw_get(
                f"{RDW_BASE}{FUEL_DATASET}.json",
                {"kenteken": plate},
                self.app_token,
            )
            fuel = fuels[0] if fuels else None
        except requests.exceptions.RequestException:
            self.log.warning("Could not fetch fuel data for %s", plate)
            fuel = None

        self.bot.privmsg(target, format_summary(plate, vehicle, fuel))

    @classmethod
    def reload(cls, old: Self) -> Self:  # pragma: no cover
        return cls(old.bot)
