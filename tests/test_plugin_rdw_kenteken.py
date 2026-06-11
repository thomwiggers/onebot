import unittest
from unittest.mock import MagicMock, patch

from onebot.plugins.rdw_kenteken import (
    format_date,
    format_drivetrain,
    format_flags,
    format_price,
    normalize_plate,
)
from onebot.testing import BotTestCase


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
        self.assertSent(
            [
                "PRIVMSG #chan :N524KT: KIA CEED Stationwagen | 2021 | Benzine 1.0L 88kW EURO 6 AP | Catalogus: €27.645 | APK: 06-08-2027 | Top: 190 km/h"
            ]
        )

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
        self.assertSent(
            [
                "PRIVMSG #chan :N524KT: KIA CEED Stationwagen | 2020 | Benzine 1.0L 88kW EURO 6 AP | Catalogus: €27.645 | APK: 06-08-2027 | Top: 190 km/h",
                "PRIVMSG #chan :⚠ N524KT: geïmporteerd",
            ]
        )


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
        assert (
            result
            == "⚠ N524KT: verdachte kilometerstand (tellerstandoordeel: Niet logisch)"
        )

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
        assert (
            format_flags("N524KT", v)
            == "⚠ N524KT: geëxporteerd, openstaande terugroepactie"
        )
