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
