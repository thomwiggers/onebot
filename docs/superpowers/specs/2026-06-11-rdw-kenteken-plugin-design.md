# RDW Kenteken Plugin Design

## Overview

IRC bot plugin that looks up Dutch vehicle registration data from the RDW open data API and returns a summary line for a given license plate.

## Command

```
!kenteken <plate>
```

Plate input is normalized: dashes and spaces stripped, uppercased. `N-524-KT`, `n524kt`, `N 524 KT` all resolve to `N524KT`.

## API

Base URL: `https://opendata.rdw.nl/resource/`

| Dataset | ID | Fields used |
|---|---|---|
| Gekentekende voertuigen | `m9d7-ebf2` | merk, handelsbenaming, inrichting, datum_eerste_toelating, catalogusprijs, vervaldatum_apk |
| Brandstof | `8ys7-d773` | brandstof_omschrijving, cilinderinhoud, nettomaximumvermogen, uitlaatemissieniveau |

Both requests use `?kenteken=<PLATE>` and `X-App-Token` header.

## Configuration

```ini
[onebot.plugins.rdw_kenteken]
app_token = <token>
```

## Output Format

Single IRC line:

```
N-524-KT: KIA CEED Stationwagen | 2021 | Benzine 1.0L 88kW Euro 6 AP | Catalogus: €27.645 | APK: 06-08-2027
```

Fields:
- Plate (formatted with dashes, RDW sidesteps this so we display raw)
- `merk` + `handelsbenaming` + `inrichting`
- Year from `datum_eerste_toelating` (first 4 chars of `YYYYMMDD`)
- `brandstof_omschrijving` + engine size in L (cilinderinhoud / 1000, 1 decimal) + power in kW (nettomaximumvermogen, rounded) + `uitlaatemissieniveau`
- Catalogus price formatted with dots as thousands separator + euro sign
- APK expiry reformatted from `YYYYMMDD` to `DD-MM-YYYY`

## Error Handling

| Condition | Response |
|---|---|
| Plate not found (empty API response) | `Kenteken niet gevonden.` |
| HTTP error | `Fout bij opvragen RDW data (HTTP <code>).` |
| Timeout | `RDW verzoek verlopen.` |
| Request exception | `RDW verzoek mislukt.` |

## Files

- `onebot/plugins/rdw_kenteken.py` — plugin
- `tests/test_plugin_rdw_kenteken.py` — tests

## Testing

Mock `requests.get` via `unittest.mock.patch`. No betamax cassettes needed.

Three test cases:
1. Happy path — known plate returns formatted line
2. Unknown plate — empty API response returns Dutch not-found message
3. HTTP error — `requests.exceptions.HTTPError` returns error message
