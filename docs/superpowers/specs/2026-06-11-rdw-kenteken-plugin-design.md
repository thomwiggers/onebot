# RDW Kenteken Plugin Design

## Overview

IRC bot plugin that looks up Dutch vehicle registration data from the RDW open data API and returns a summary line for a given license plate.

## Command

```
!rdw <plate>
```

Plate input is normalized: dashes and spaces stripped, uppercased. `N-524-KT`, `n524kt`, `N 524 KT` all resolve to `N524KT`.

## API

Base URL: `https://opendata.rdw.nl/resource/`

| Dataset | ID | Fields used |
|---|---|---|
| Gekentekende voertuigen | `m9d7-ebf2` | merk, handelsbenaming, inrichting, datum_eerste_toelating, datum_eerste_tenaamstelling_in_nederland, catalogusprijs, vervaldatum_apk, cilinderinhoud, maximale_constructiesnelheid, export_indicator, openstaande_terugroepactie_indicator, tellerstandoordeel, wacht_op_keuren |
| Terugroepactie status | `t49b-isb7` | (checked for any records) |
| Brandstof | `8ys7-d773` | brandstof_omschrijving, nettomaximumvermogen, uitlaatemissieniveau |

All requests use `?kenteken=<PLATE>` and `X-App-Token` header. Engine size (`cilinderinhoud`) comes from the main dataset; fuel type and power from brandstof.

## Configuration

```ini
[onebot.plugins.rdw_kenteken]
rdw_app_token = <token>
```

## Output Format

Single IRC line:

```
N-524-KT: KIA CEED Stationwagen | 2021 | Benzine 1.0L 88kW Euro 6 AP | Catalogus: €27.645 | APK: 06-08-2027 | Top: 190 km/h
```

Fields:
- Plate (formatted with dashes, RDW sidesteps this so we display raw)
- `merk` + `handelsbenaming` + `inrichting`
- Year from `datum_eerste_toelating` (first 4 chars of `YYYYMMDD`)
- `brandstof_omschrijving` + engine size in L (cilinderinhoud / 1000, 1 decimal) + power in kW (nettomaximumvermogen, rounded) + `uitlaatemissieniveau`
- Catalogus price formatted with dots as thousands separator + euro sign
- APK expiry reformatted from `YYYYMMDD` to `DD-MM-YYYY`
- `maximale_constructiesnelheid` in km/h

## Flags (optional second message)

Only sent if one or more flags apply. Format: `⚠ N-524-KT: <flag>, <flag>, ...`

| Condition | Field | Flag text |
|---|---|---|
| Imported | `datum_eerste_toelating` predates `datum_eerste_tenaamstelling_in_nederland` by >30 days | `geïmporteerd` |
| Exported | `export_indicator == "Ja"` | `geëxporteerd` |
| Suspicious mileage | `tellerstandoordeel != "Logisch"` | `verdachte kilometerstand (tellerstandoordeel: <value>)` |
| Open recall | `openstaande_terugroepactie_indicator == "Ja"` | `openstaande terugroepactie` |
| Pending inspection | `wacht_op_keuren != "Geen verstrekking in Open Data"` | `wacht op keuren: <value>` |

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
