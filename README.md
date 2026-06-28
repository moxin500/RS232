# RS232

This script reads aircraft telemetry from a laptop serial/RS-232 input, normalizes the data into a common JSON telemetry payload, sends it over UDP to another device, and logs every decoded packet to CSV.

It was built for the Cozy Mk IV computer-vision flight-test workflow, where the Android app or another local tool needs live aircraft state such as IAS, pitch, roll, altitude, RPM, fuel flow, and GPS speed while recording or analyzing video.

## What this is

This is a general bridge for line-oriented serial telemetry:

```text
RS-232 / USB serial adapter -> laptop Python script -> UDP JSON packets -> Android app / desktop listener
                                      |
                                      +-> CSV packet log
```

It can be used by other Cozy project teams when they need one of the following:

- live aircraft data streamed to a phone, laptop, or analysis tool;
- a CSV log of decoded telemetry packets;
- a parser bench test using saved RS-232 text instead of a live aircraft connection;
- a raw byte monitor to verify that the laptop is receiving serial data;
- a Garmin DLE binary packet monitor for low-level debugging.

## Important limitation

This is not a universal RS-232 decoder. RS-232 only describes the electrical/serial transport. The actual meaning of the bytes depends on the avionics output format.

The bridge is generalizable in two ways:

1. **Transport layer:** serial read, UDP send, CSV logging, dry-run mode, port listing, and raw monitoring are reusable across teams.
2. **Line formats:** CSV, JSON, and raw line passthrough are reusable if another team can output telemetry in those formats.

The Garmin fixed-width text parsing is specific to the Garmin text output format used in this project. The hard-coded slices for `=1`, `=3`, `=5`, and `@` records should be treated as protocol-specific, not aircraft-universal.

## Supported input formats

The script supports these `--line-format` values:

| Format | Meaning |
| --- | --- |
| `auto` | Detects JSON lines, Garmin text records, or CSV lines automatically. This is the default. |
| `garmin-text` | Parses Garmin text records beginning with `=`, plus GPS records beginning with `@`. |
| `csv` | Parses comma-separated telemetry. Can learn a header row or use `--csv-fields`. |
| `json` | Parses one JSON object per line. |
| `raw` | Sends the raw serial line inside the JSON payload without interpreting fields. |

## Garmin records currently decoded

### `@` GPS record

Decoded fields include:

- `utc_time`
- `latitude_deg`
- `longitude_deg`
- `gps_ground_speed_kt`
- `gps_altitude_ft`
- `gps_track_deg`

### `=1` attitude / air-data record

Decoded fields include:

- `utc_time`
- `pitch_deg`
- `roll_deg`
- `heading_deg`
- `ias_kt`
- `pressure_altitude_ft`
- `rate_of_turn_deg_s`
- `lateral_acceleration_g`
- `normal_acceleration_g`
- `vertical_speed_fpm`
- `oat_deg_c`
- `baro_in_hg`
- `aoa_raw`

Current important field slices:

```text
roll_deg               = line[15:20] / 10
heading_deg            = line[20:23]
ias_kt                 = line[23:27] / 10
pressure_altitude_ft   = line[27:33]
vertical_speed_fpm     = line[45:49] * 10
oat_deg_c              = line[49:52]
baro_in_hg             = 27.50 + line[52:55] / 100
```

### `=3` engine record

Decoded fields include:

- `oil_pressure`
- `oil_temp`
- `rpm`
- `manifold_pressure_in_hg`
- `fuel_flow_gph`
- `fuel_pressure_psi`
- `fuel_quantity_1_gal`
- `fuel_quantity_2_gal`
- `fuel_remaining_gal`
- `volts_1`
- `volts_2`
- `amps_1`

Current important field slices:

```text
rpm                    = line[18:22]
manifold_pressure_in_hg = line[26:29] / 10
fuel_flow_gph           = line[29:32] / 10
fuel_pressure_psi       = line[35:38] / 10
fuel_quantity_1_gal     = line[38:41] / 10
fuel_quantity_2_gal     = line[41:44] / 10
fuel_remaining_gal      = line[44:47] / 10
volts_1                 = line[47:50] / 10
volts_2                 = line[50:53] / 10
amps_1                  = line[53:57] / 10
```

### `=5` EIS record

The bridge captures generic EIS sensor ID/value pairs as `garmin_eis_values` when present. It does **not** use `=5` values for RPM in the current Cozy workflow.

## Output JSON schema

Every UDP packet is a JSON object with this basic structure:

```json
{
  "schema": "canard_cv.garmin.telemetry.v1",
  "source": "garmin_rs232_bridge",
  "sequence": 0,
  "utc_time": "12:34:56Z",
  "received_wall_time": "2026-06-27T20:00:00Z",
  "ias_kt": 82.5,
  "pitch_deg": 3.1,
  "roll_deg": -1.4,
  "heading_deg": 245.0,
  "vertical_speed_fpm": 120.0,
  "pressure_altitude_ft": 6200.0,
  "rpm": 2450.0,
  "manifold_pressure_in_hg": 23.8,
  "fuel_flow_gph": 8.7,
  "gps_ground_speed_kt": 91.0,
  "raw_serial_line": "...original input line..."
}
```

Missing values are sent as `null`. When Garmin records arrive in separate packets, the bridge carries forward the most recent valid values so a downstream app can receive one combined live telemetry state. If a fresh Garmin fixed-width field is blank or contains `_`, the bridge clears that stale value instead of carrying old data forward.

## Requirements

Python 3.10+ is recommended. The script uses the standard library plus `pyserial` for live serial-port access.

Install the dependency:

```powershell
py -m pip install pyserial
```

Or add this to `requirements.txt`:

```text
pyserial>=3.5
```

## Suggested repo location

Suggested file layout:

```text
canard_cv_codex_starter/
  tools/
    garmin_rs232_udp_bridge.py
  outputs/
    .gitkeep
  README_RS232_TELEMETRY_BRIDGE.md
  requirements.txt
```

The current script resolves relative log paths assuming it lives one folder below the repository root, such as `tools/garmin_rs232_udp_bridge.py`. If you place it directly in the repo root, change this line:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
```

to:

```python
REPO_ROOT = Path(__file__).resolve().parent
```

Also, if you want the file to be executable on Linux/macOS, make sure the shebang is the first line of the file:

```python
#!/usr/bin/env python3
```

Move any personal comment above it to a normal comment below the shebang.

## Quick start

### 1. Find the serial port

```powershell
py tools\garmin_rs232_udp_bridge.py --list-ports
```

Look for the USB serial adapter. On Windows it will usually be something like `COM10` or `COM11`.

### 2. Confirm bytes are arriving

Use this before trying to decode data:

```powershell
py tools\garmin_rs232_udp_bridge.py --port COM11 --baud 115200 --monitor-bytes
```

If the aircraft output is configured for a different baud rate, change `--baud`. Common values are `9600` and `115200`; use the value that matches the avionics/adapter setup.

### 3. Dry-run the parser without sending UDP

```powershell
py tools\garmin_rs232_udp_bridge.py ^
  --port COM11 ^
  --baud 115200 ^
  --udp-host 127.0.0.1 ^
  --dry-run ^
  --print-packets ^
  --print-raw ^
  --line-format auto ^
  --log outputs\garmin_rs232_udp_packets.csv
```

`--dry-run` still requires `--udp-host`, but it does not actually send UDP packets.

### 4. Send live UDP to a phone or another laptop

Use the receiving device IP address shown by the Android telemetry panel or your network settings:

```powershell
py tools\garmin_rs232_udp_bridge.py ^
  --port COM11 ^
  --baud 115200 ^
  --udp-host 192.168.1.42 ^
  --udp-port 49005 ^
  --line-format auto ^
  --print-packets ^
  --log outputs\garmin_rs232_udp_packets.csv
```

If using subnet broadcast instead of a specific phone IP:

```powershell
py tools\garmin_rs232_udp_bridge.py ^
  --port COM11 ^
  --baud 115200 ^
  --udp-host 192.168.1.255 ^
  --broadcast ^
  --udp-port 49005
```

Windows Firewall may need to allow outbound UDP from Python.

## Bench testing with saved data

You can test parsing from a text file without a serial adapter:

```powershell
type saved_rs232_lines.txt | py tools\garmin_rs232_udp_bridge.py ^
  --stdin ^
  --udp-host 127.0.0.1 ^
  --dry-run ^
  --print-packets ^
  --line-format auto ^
  --log outputs\bench_rs232_packets.csv
```

For a short test:

```powershell
type saved_rs232_lines.txt | py tools\garmin_rs232_udp_bridge.py ^
  --stdin ^
  --udp-host 127.0.0.1 ^
  --dry-run ^
  --print-packets ^
  --max-packets 50
```

## CSV input mode for non-Garmin teams

If another team has a microcontroller, DAQ, or separate script producing CSV lines, they can still use the bridge.

With a CSV header row:

```text
utc_time,ias_kt,pitch_deg,roll_deg,rpm,gps_ground_speed_kt
12:00:01Z,82.5,3.1,-1.4,2450,91.0
```

Run:

```powershell
py tools\garmin_rs232_udp_bridge.py --port COM11 --baud 115200 --udp-host 192.168.1.42 --line-format csv
```

Without a CSV header row, provide the field order:

```powershell
py tools\garmin_rs232_udp_bridge.py ^
  --port COM11 ^
  --baud 115200 ^
  --udp-host 192.168.1.42 ^
  --line-format csv ^
  --csv-fields utc_time,ias_kt,pitch_deg,roll_deg,rpm,gps_ground_speed_kt
```

## JSON input mode for non-Garmin teams

If another team can output one JSON object per line, the bridge will normalize recognized aliases into the standard schema and preserve extra keys.

Example input line:

```json
{"time":"12:00:01Z","ias":82.5,"pitch":3.1,"roll":-1.4,"rpm":2450,"custom_sensor":"test"}
```

Run:

```powershell
py tools\garmin_rs232_udp_bridge.py --port COM11 --baud 115200 --udp-host 192.168.1.42 --line-format json
```

## Packet log

Every sent or dry-run packet is written to CSV. Default path:

```text
outputs/garmin_rs232_udp_packets.csv
```

Logged columns:

- `sent_wall_time_s`
- `sequence`
- `serial_port`
- `udp_host`
- `udp_port`
- `utc_time`
- `ias_kt`
- `pitch_deg`
- `roll_deg`
- `rpm`
- `payload_bytes`
- `payload_json`

The `payload_json` column is the full UDP payload and is the best source for downstream replay or debugging.

## Recommended validation before flight/test use

Before another team relies on this, run this checklist:

1. Verify the COM port appears with `--list-ports`.
2. Verify bytes arrive with `--monitor-bytes`.
3. Verify the baud rate is correct. Wrong baud usually produces garbage or no useful lines.
4. Run `--dry-run --print-packets --print-raw` and confirm the decoded values make physical sense.
5. Confirm IAS formatting on Garmin `=1` records. Example: raw `0145` should decode to `14.5 kt`.
6. Confirm RPM comes from Garmin `=3` records, not `=5` records.
7. Confirm engine-off or invalid values clear stale data instead of carrying old values forever.
8. Confirm the receiver is on the same network and listening on the selected UDP port.
9. Save a short packet log from every test configuration so issues can be replayed later.

## Known limitations and future improvements

Current limitations:

- Garmin fixed-width text slices are hard-coded.
- Garmin `=1` / `=3` checksum text is captured but not fully validated before accepting the packet.
- Garmin binary packets are monitored but not converted into the live telemetry JSON stream.
- The bridge assumes line-oriented input for normal UDP forwarding.
- UDP is fire-and-forget. There is no receiver acknowledgement or guaranteed delivery.
- The payload schema is named `canard_cv.garmin.telemetry.v1`; if this becomes project-wide beyond Garmin, consider renaming the next version to something like `canard_cv.telemetry.v2`.

Useful future improvements:

- Add unit tests with saved Garmin sample lines.
- Add checksum validation for Garmin text records.
- Move Garmin parsing into a separate module such as `garmin_text.py`.
- Add a `--no-carry-forward` option for teams that want each record to contain only fresh values.
- Add a replay script that reads `payload_json` from a packet log and re-sends it over UDP.
- Add a small schema document listing field names, units, and meanings.

## Field units

| Field | Unit |
| --- | --- |
| `ias_kt` | knots |
| `tas_kt` | knots |
| `pitch_deg` | degrees |
| `roll_deg` | degrees |
| `heading_deg` | degrees |
| `rate_of_turn_deg_s` | degrees/second |
| `lateral_acceleration_g` | g |
| `normal_acceleration_g` | g |
| `vertical_speed_fpm` | feet/minute |
| `pressure_altitude_ft` | feet |
| `density_altitude_ft` | feet |
| `agl_ft` | feet |
| `oat_deg_c` | degrees C |
| `baro_in_hg` | inches Hg |
| `rpm` | revolutions/minute |
| `manifold_pressure_in_hg` | inches Hg |
| `oil_pressure` | as reported by source; likely psi |
| `oil_temp` | as reported by source; likely degrees F or C depending avionics config |
| `fuel_pressure_psi` | psi |
| `fuel_quantity_1_gal` | gallons |
| `fuel_quantity_2_gal` | gallons |
| `fuel_remaining_gal` | gallons |
| `volts_1` | volts |
| `volts_2` | volts |
| `amps_1` | amps |
| `engine_power_pct` | percent |
| `fuel_flow_gph` | gallons/hour |
| `latitude_deg` | decimal degrees |
| `longitude_deg` | decimal degrees |
| `gps_ground_speed_kt` | knots |
| `gps_altitude_ft` | feet |
| `gps_track_deg` | degrees |
| `gps_vertical_velocity_mps` | meters/second |

## Bottom line for other teams

Other Cozy teams can use this safely as a shared telemetry bridge if they understand the boundary:

- use it directly for the same Garmin RS-232 text output;
- use CSV or JSON modes for other telemetry producers;
- do not assume arbitrary RS-232 data can be interpreted without writing a parser for that device's protocol.
