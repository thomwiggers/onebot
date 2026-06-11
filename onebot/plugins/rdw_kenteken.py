import re
import logging


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
