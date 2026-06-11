# RDW Kenteken Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `!rdw <plate>` IRC command that queries the Dutch RDW open data API and returns vehicle info for a given license plate, with an optional second message flagging suspicious conditions.

**Architecture:** A single plugin file with pure helper functions (normalize, format) plus an `@irc3.plugin` class whose `@command rdw` method makes two HTTP requests (main vehicle dataset + fuel sub-dataset), formats the result as one IRC line, and optionally sends a second line with flags. Tests use `unittest.mock.patch` to intercept `requests.get`.

**Tech Stack:** Python 3.11+, irc3, requests, unittest.mock

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `onebot/plugins/rdw_kenteken.py` | Create | Plugin: helpers, API fetchers, formatter, irc3 plugin class |
| `tests/test_plugin_rdw_kenteken.py` | Create | Unit tests for helpers + integration tests via BotTestCase |

---

### Task 1: Helper functions + unit tests

**Files:**
- Create: `onebot/plugins/rdw_kenteken.py`
- Create: `tests/test_plugin_rdw_kenteken.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plugin_rdw_kenteken.py`:

```python
import unittest
from onebot.plugins.rdw_kenteken import (
    normalize_plate,
    format_date,
    format_price,
    format_drivetrain,
)


class NormalizePlateTest(unittest.TestCase):
    def test_strips_dashes(self):
        assert normalize_plate("N-524-KT") == "N524KT"

    def test_strips_spaces(self):
        assert normalize_plate("N 524 KT") == "N524KT"

    def test_uppercases(self):
        assert normalize_plate("n524kt") == "N524KT"

    def test_already_normalized(self):
        assert normalize_plate("N524KT") == "N524KT"


class FormatDateTest(unittest.TestCase):
    def test_formats_date(self):
        assert format_date("20270806") == "06-08-2027"


class FormatPriceTest(unittest.TestCase):
    def test_thousands_separator(self):
        assert format_price("27645") == "€27.645"

    def test_large_price(self):
        assert format_price("127645") == "€127.645"

    def test_small_price(self):
        assert format_price("999") == "€999"


class FormatDrivetrainTest(unittest.TestCase):
    def test_with_full_fuel_record(self):
        result = format_drivetrain(
            {"cilinderinhoud": "998"},
            {
                "brandstof_omschrijving": "Benzine",
                "nettomaximumvermogen": "88.30",
                "uitlaatemissieniveau": "EURO 6 AP",
            },
        )
        assert result == "Benzine 1.0L 88kW EURO 6 AP"

    def test_without_fuel(self):
        assert format_drivetrain({"cilinderinhoud": "1598"}, None) == "1.6L"

    def test_rounds_power(self):
        result = format_drivetrain(
            {"cilinderinhoud": "1995"},
            {
                "brandstof_omschrijving": "Diesel",
                "nettomaximumvermogen": "110.50",
                "uitlaatemissieniveau": "EURO 6 D",
            },
        )
        assert result == "Diesel 2.0L 111kW EURO 6 D"
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_plugin_rdw_kenteken.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement the helpers**

Create `onebot/plugins/rdw_kenteken.py`:

```python
import re
import logging
from datetime import date
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
            parts.append(f"{round(float(fuel['nettomaximumvermogen']))}kW")
        if fuel.get("uitlaatemissieniveau"):
            parts.append(fuel["uitlaatemissieniveau"])
    return " ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_plugin_rdw_kenteken.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add onebot/plugins/rdw_kenteken.py tests/test_plugin_rdw_kenteken.py
git commit -m "feat(rdw): add helper functions with tests"
```

---

### Task 2: Plugin class + happy path

**Files:**
- Modify: `onebot/plugins/rdw_kenteken.py`
- Modify: `tests/test_plugin_rdw_kenteken.py`

- [ ] **Step 1: Add the integration test**

Append to `tests/test_plugin_rdw_kenteken.py`:

```python
from unittest.mock import MagicMock, patch
from onebot.testing import BotTestCase


VEHICLE_RECORD = {
    "kenteken": "N524KT",
    "merk": "KIA",
    "handelsbenaming": "CEED",
    "inrichting": "stationwagen",
    "datum_eerste_toelating": "20211115",
    "datum_eerste_tenaamstelling_in_nederland": "20211115",
    "catalogusprijs": "27645",
    "vervaldatum_apk": "20270806",
    "cilinderinhoud": "998",
    "maximale_constructiesnelheid": "190",
    "export_indicator": "Nee",
    "openstaande_terugroepactie_indicator": "Nee",
    "tellerstandoordeel": "Logisch",
    "wacht_op_keuren": "Geen verstrekking in Open Data",
}

FUEL_RECORD = {
    "kenteken": "N524KT",
    "brandstof_omschrijving": "Benzine",
    "nettomaximumvermogen": "88.30",
    "uitlaatemissieniveau": "EURO 6 AP",
}


def _mock_response(data):
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


class RdwCommandTestCase(BotTestCase):
    config = {
        "includes": ["onebot.plugins.rdw_kenteken", "irc3.plugins.command"],
        "cmd": "!",
        "onebot.plugins.rdw_kenteken": {"rdw_app_token": "test-token"},
    }

    def setUp(self):
        super().setUp()
        self.callFTU()

    @patch("onebot.plugins.rdw_kenteken.requests.get")
    def test_happy_path(self, mock_get):
        mock_get.side_effect = [
            _mock_response([VEHICLE_RECORD]),
            _mock_response([FUEL_RECORD]),
        ]
        self.bot.dispatch(":user!user@host PRIVMSG #chan :!rdw N-524-KT")
        self.assertSent([
            "PRIVMSG #chan :N524KT: KIA CEED Stationwagen | 2021 | Benzine 1.0L 88kW EURO 6 AP | Catalogus: €27.645 | APK: 06-08-2027 | Top: 190 km/h"
        ])
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_plugin_rdw_kenteken.py::RdwCommandTestCase::test_happy_path -v
```

Expected: FAIL — plugin class not defined yet.

- [ ] **Step 3: Add `_rdw_get`, `format_summary`, and plugin class to `onebot/plugins/rdw_kenteken.py`**

Append after `format_drivetrain`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_plugin_rdw_kenteken.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add onebot/plugins/rdw_kenteken.py tests/test_plugin_rdw_kenteken.py
git commit -m "feat(rdw): add plugin class and happy path"
```

---

### Task 3: Flags

**Files:**
- Modify: `onebot/plugins/rdw_kenteken.py`
- Modify: `tests/test_plugin_rdw_kenteken.py`

- [ ] **Step 1: Add flag unit tests and integration test**

Append to `tests/test_plugin_rdw_kenteken.py`:

```python
from onebot.plugins.rdw_kenteken import format_flags


class FormatFlagsTest(unittest.TestCase):
    def test_no_flags_returns_none(self):
        assert format_flags("N524KT", VEHICLE_RECORD) is None

    def test_imported_when_nl_registration_much_later(self):
        v = {
            **VEHICLE_RECORD,
            "datum_eerste_toelating": "20200101",
            "datum_eerste_tenaamstelling_in_nederland": "20211115",
        }
        assert format_flags("N524KT", v) == "⚠ N524KT: geïmporteerd"

    def test_not_imported_when_same_day(self):
        assert format_flags("N524KT", VEHICLE_RECORD) is None

    def test_exported(self):
        v = {**VEHICLE_RECORD, "export_indicator": "Ja"}
        assert format_flags("N524KT", v) == "⚠ N524KT: geëxporteerd"

    def test_suspicious_mileage(self):
        v = {**VEHICLE_RECORD, "tellerstandoordeel": "Niet logisch"}
        result = format_flags("N524KT", v)
        assert result == "⚠ N524KT: verdachte kilometerstand (tellerstandoordeel: Niet logisch)"

    def test_open_recall(self):
        v = {**VEHICLE_RECORD, "openstaande_terugroepactie_indicator": "Ja"}
        assert format_flags("N524KT", v) == "⚠ N524KT: openstaande terugroepactie"

    def test_pending_inspection(self):
        v = {**VEHICLE_RECORD, "wacht_op_keuren": "Wacht op keuren"}
        assert format_flags("N524KT", v) == "⚠ N524KT: wacht op keuren: Wacht op keuren"

    def test_multiple_flags_combined(self):
        v = {
            **VEHICLE_RECORD,
            "export_indicator": "Ja",
            "openstaande_terugroepactie_indicator": "Ja",
        }
        assert format_flags("N524KT", v) == "⚠ N524KT: geëxporteerd, openstaande terugroepactie"
```

Also add this integration test inside `RdwCommandTestCase`:

```python
    @patch("onebot.plugins.rdw_kenteken.requests.get")
    def test_flags_imported_sends_second_message(self, mock_get):
        imported_vehicle = {
            **VEHICLE_RECORD,
            "datum_eerste_toelating": "20200101",
            "datum_eerste_tenaamstelling_in_nederland": "20211115",
        }
        mock_get.side_effect = [
            _mock_response([imported_vehicle]),
            _mock_response([FUEL_RECORD]),
        ]
        self.bot.dispatch(":user!user@host PRIVMSG #chan :!rdw N524KT")
        self.assertSent([
            "PRIVMSG #chan :N524KT: KIA CEED Stationwagen | 2020 | Benzine 1.0L 88kW EURO 6 AP | Catalogus: €27.645 | APK: 06-08-2027 | Top: 190 km/h",
            "PRIVMSG #chan :⚠ N524KT: geïmporteerd",
        ])
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_plugin_rdw_kenteken.py::FormatFlagsTest -v
```

Expected: `ImportError` — `format_flags` not defined yet.

- [ ] **Step 3: Implement `format_flags` and wire into command**

Add `format_flags` to `onebot/plugins/rdw_kenteken.py` after `format_summary`:

```python
def format_flags(plate: str, vehicle: dict) -> str | None:
    """Return a warning line if suspicious conditions apply, else None."""
    flags = []

    first_toelating = vehicle.get("datum_eerste_toelating", "")
    first_nl = vehicle.get("datum_eerste_tenaamstelling_in_nederland", "")
    if first_toelating and first_nl:
        dt_toelating = date(
            int(first_toelating[:4]),
            int(first_toelating[4:6]),
            int(first_toelating[6:8]),
        )
        dt_nl = date(
            int(first_nl[:4]),
            int(first_nl[4:6]),
            int(first_nl[6:8]),
        )
        if (dt_nl - dt_toelating).days > 30:
            flags.append("geïmporteerd")

    if vehicle.get("export_indicator") == "Ja":
        flags.append("geëxporteerd")

    tellerstand = vehicle.get("tellerstandoordeel", "Logisch")
    if tellerstand and tellerstand != "Logisch":
        flags.append(
            f"verdachte kilometerstand (tellerstandoordeel: {tellerstand})"
        )

    if vehicle.get("openstaande_terugroepactie_indicator") == "Ja":
        flags.append("openstaande terugroepactie")

    wacht = vehicle.get("wacht_op_keuren", "Geen verstrekking in Open Data")
    if wacht and wacht != "Geen verstrekking in Open Data":
        flags.append(f"wacht op keuren: {wacht}")

    if not flags:
        return None

    return f"⚠ {plate}: {', '.join(flags)}"
```

Then update the `rdw` command in `RdwKentekenPlugin` to send the flags message. Replace the last two lines of the command:

```python
        # replace:
        self.bot.privmsg(target, format_summary(plate, vehicle, fuel))

        # with:
        self.bot.privmsg(target, format_summary(plate, vehicle, fuel))
        flags = format_flags(plate, vehicle)
        if flags:
            self.bot.privmsg(target, flags)
```

- [ ] **Step 4: Run all tests**

```
uv run pytest tests/test_plugin_rdw_kenteken.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add onebot/plugins/rdw_kenteken.py tests/test_plugin_rdw_kenteken.py
git commit -m "feat(rdw): add flags for suspicious vehicle conditions"
```

---

### Task 4: Error handling

**Files:**
- Modify: `onebot/plugins/rdw_kenteken.py`
- Modify: `tests/test_plugin_rdw_kenteken.py`

- [ ] **Step 1: Add error handling tests inside `RdwCommandTestCase`**

```python
    @patch("onebot.plugins.rdw_kenteken.requests.get")
    def test_plate_not_found(self, mock_get):
        mock_get.return_value = _mock_response([])
        self.bot.dispatch(":user!user@host PRIVMSG #chan :!rdw XXXXXX")
        self.assertSent(["PRIVMSG #chan :Kenteken niet gevonden."])

    @patch("onebot.plugins.rdw_kenteken.requests.get")
    def test_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError(response=mock_response)
        )
        self.bot.dispatch(":user!user@host PRIVMSG #chan :!rdw N524KT")
        self.assertSent(["PRIVMSG #chan :Fout bij opvragen RDW data (HTTP 500)."])

    @patch("onebot.plugins.rdw_kenteken.requests.get")
    def test_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        self.bot.dispatch(":user!user@host PRIVMSG #chan :!rdw N524KT")
        self.assertSent(["PRIVMSG #chan :RDW verzoek verlopen."])

    @patch("onebot.plugins.rdw_kenteken.requests.get")
    def test_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        self.bot.dispatch(":user!user@host PRIVMSG #chan :!rdw N524KT")
        self.assertSent(["PRIVMSG #chan :RDW verzoek mislukt."])
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_plugin_rdw_kenteken.py::RdwCommandTestCase::test_http_error tests/test_plugin_rdw_kenteken.py::RdwCommandTestCase::test_timeout tests/test_plugin_rdw_kenteken.py::RdwCommandTestCase::test_request_exception -v
```

Expected: FAIL — no error handling in command yet.

- [ ] **Step 3: Wrap the main fetch in error handling**

Replace the `vehicles = _rdw_get(...)` block in `RdwKentekenPlugin.rdw` with:

```python
        try:
            vehicles = _rdw_get(
                f"{RDW_BASE}{VEHICLE_DATASET}.json",
                {"kenteken": plate},
                self.app_token,
            )
        except requests.exceptions.Timeout:
            self.bot.privmsg(target, "RDW verzoek verlopen.")
            return
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            self.bot.privmsg(target, f"Fout bij opvragen RDW data (HTTP {code}).")
            return
        except requests.exceptions.RequestException:
            self.log.exception("RDW request failed for plate %s", plate)
            self.bot.privmsg(target, "RDW verzoek mislukt.")
            return
```

- [ ] **Step 4: Run all tests**

```
uv run pytest tests/test_plugin_rdw_kenteken.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full test suite + linters**

```
uv run ruff format .
uv run ruff check --fix .
uv run ruff check .
uv run pytest --doctest-modules -v
```

Expected: no errors or failures.

- [ ] **Step 6: Commit**

```bash
git add onebot/plugins/rdw_kenteken.py tests/test_plugin_rdw_kenteken.py
git commit -m "feat(rdw): add error handling for API failures"
```
