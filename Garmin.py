
#!/usr/bin/env python3
from __future__ import annotations

#*Will built this bridge*


import argparse
import csv
import json
import math
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

TELEMETRY_FIELDS = [
    "ias_kt",
    "tas_kt",
    "pitch_deg",
    "roll_deg",
    "heading_deg",
    "rate_of_turn_deg_s",
    "lateral_acceleration_g",
    "vertical_speed_fpm",
    "normal_acceleration_g",
    "pressure_altitude_ft",
    "density_altitude_ft",
    "agl_ft",
    "oat_deg_c",
    "baro_in_hg",
    "rpm",
    "manifold_pressure_in_hg",
    "oil_pressure",
    "oil_temp",
    "fuel_pressure_psi",
    "fuel_quantity_1_gal",
    "fuel_quantity_2_gal",
    "fuel_remaining_gal",
    "volts_1",
    "volts_2",
    "amps_1",
    "engine_power_pct",
    "fuel_flow_gph",
    "latitude_deg",
    "longitude_deg",
    "gps_ground_speed_kt",
    "gps_altitude_ft",
    "gps_track_deg",
    "gps_vertical_velocity_mps",
]

FIELD_ALIASES: Dict[str, Sequence[str]] = {
    "ias_kt": ("ias_kt", "ias", "indicated_airspeed_kt", "raw_ias"),
    "tas_kt": ("tas_kt", "tas", "true_airspeed_kt", "raw_tas"),
    "pitch_deg": ("pitch_deg", "pitch", "raw_pitch"),
    "roll_deg": ("roll_deg", "roll", "raw_roll"),
    "heading_deg": ("heading_deg", "heading", "raw_heading"),
    "rate_of_turn_deg_s": ("rate_of_turn_deg_s", "rate_of_turn", "turn_rate", "raw_rate_of_turn"),
    "lateral_acceleration_g": ("lateral_acceleration_g", "lateral_accel", "raw_lateral_accel"),
    "vertical_speed_fpm": ("vertical_speed_fpm", "vspd", "vertical_speed_ft_min", "raw_vspd"),
    "normal_acceleration_g": ("normal_acceleration_g", "normac", "raw_normac"),
    "pressure_altitude_ft": ("pressure_altitude_ft", "altp", "raw_altp"),
    "density_altitude_ft": ("density_altitude_ft", "altd", "raw_altd"),
    "agl_ft": ("agl_ft", "agl", "raw_agl"),
    "oat_deg_c": ("oat_deg_c", "oat", "raw_oat"),
    "baro_in_hg": ("baro_in_hg", "altimeter_in_hg", "raw_baro"),
    "rpm": ("rpm", "e1_rpm", "raw_e1_rpm"),
    "manifold_pressure_in_hg": ("manifold_pressure_in_hg", "e1_map", "raw_e1_map"),
    "oil_pressure": ("oil_pressure", "oil_pressure_psi", "raw_oil_pressure"),
    "oil_temp": ("oil_temp", "oil_temp_deg", "raw_oil_temp"),
    "fuel_pressure_psi": ("fuel_pressure_psi", "fuel_pressure", "raw_fuel_pressure"),
    "fuel_quantity_1_gal": ("fuel_quantity_1_gal", "fuel_qty_1", "raw_fuel_qty_1"),
    "fuel_quantity_2_gal": ("fuel_quantity_2_gal", "fuel_qty_2", "raw_fuel_qty_2"),
    "fuel_remaining_gal": ("fuel_remaining_gal", "fuel_remaining", "raw_fuel_remaining"),
    "volts_1": ("volts_1", "voltage_1", "raw_volts_1"),
    "volts_2": ("volts_2", "voltage_2", "raw_volts_2"),
    "amps_1": ("amps_1", "raw_amps_1"),
    "engine_power_pct": ("engine_power_pct", "e1_pctpwr", "e1_pwr", "engine_power", "raw_e1_pctpwr"),
    "fuel_flow_gph": ("fuel_flow_gph", "e1_fflow", "fuel_flow_gal_hour", "raw_e1_fflow"),
    "latitude_deg": ("latitude_deg", "lat", "latitude"),
    "longitude_deg": ("longitude_deg", "lon", "longitude"),
    "gps_ground_speed_kt": ("gps_ground_speed_kt", "gndspd", "raw_gndspd"),
    "gps_altitude_ft": ("gps_altitude_ft", "gps_altitude", "raw_gps_altitude"),
    "gps_track_deg": ("gps_track_deg", "gps_track", "track_deg", "raw_gps_track"),
    "gps_vertical_velocity_mps": ("gps_vertical_velocity_mps", "gpsvelu", "raw_gpsvelu"),
}

TIME_ALIASES = ("utc_time", "time_utc", "raw_utc_time", "timestamp", "time")

DEFAULT_CSV_FIELDS = [
    "utc_time",
    "ias_kt",
    "tas_kt",
    "pitch_deg",
    "roll_deg",
    "vertical_speed_fpm",
    "normal_acceleration_g",
    "pressure_altitude_ft",
    "density_altitude_ft",
    "agl_ft",
    "oat_deg_c",
    "rpm",
    "manifold_pressure_in_hg",
    "engine_power_pct",
    "fuel_flow_gph",
    "gps_ground_speed_kt",
    "gps_vertical_velocity_mps",
]


def repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def import_serial() -> Any:
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "pyserial is not installed. Run: py -m pip install pyserial "
            "or install project requirements with: py -m pip install -r requirements.txt"
        ) from exc
    return serial


def import_list_ports() -> Any:
    try:
        import serial.tools.list_ports as list_ports  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "pyserial is not installed. Run: py -m pip install pyserial "
            "or install project requirements with: py -m pip install -r requirements.txt"
        ) from exc
    return list_ports


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def get_first(row: Mapping[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return value
    return None


def normalize_utc_time(row: Mapping[str, Any]) -> str | None:
    value = get_first(row, TIME_ALIASES)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_payload(row: Mapping[str, Any], sequence: int, source: str, raw_line: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": "canard_cv.garmin.telemetry.v1",
        "source": source,
        "sequence": sequence,
        "utc_time": normalize_utc_time(row),
        "received_wall_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    for field in TELEMETRY_FIELDS:
        payload[field] = safe_float(get_first(row, FIELD_ALIASES.get(field, (field,))))
    for key, value in row.items():
        if key in payload or key.startswith("_"):
            continue
        payload[key] = value
    if raw_line is not None:
        payload["raw_serial_line"] = raw_line
    return payload


def should_enable_broadcast(host: str, explicit_broadcast: bool) -> bool:
    return explicit_broadcast or host == "255.255.255.255" or host.endswith(".255")


def parse_csv_fields(text: str) -> list[str]:
    fields = [field.strip() for field in text.split(",") if field.strip()]
    if not fields:
        raise SystemExit("--csv-fields cannot be blank")
    return fields


def parse_csv_line(line: str) -> list[str]:
    return next(csv.reader([line]))


def looks_like_csv_header(cells: Sequence[str]) -> bool:
    normalized = {cell.strip().lower() for cell in cells}
    known = {"utc_time", "ias", "ias_kt", "pitch", "pitch_deg", "roll", "roll_deg", "rpm", "e1_rpm"}
    return len(normalized.intersection(known)) >= 2


def parse_int_field(text: str, scale: float = 1.0) -> float | None:
    if not text or "_" in text:
        return None
    try:
        return int(text) / scale
    except ValueError:
        return None


def multiply_if_present(value: float | None, factor: float) -> float | None:
    return None if value is None else value * factor


def parse_baro_in_hg(text: str) -> float | None:
    offset = parse_int_field(text)
    return None if offset is None else 27.50 + offset / 100.0


def invalid_numeric_field(text: str) -> bool:
    return not text.strip() or "_" in text


def format_garmin_time(value: str) -> str | None:
    if len(value) < 6 or not value[:6].isdigit():
        return None
    hh = value[0:2]
    mm = value[2:4]
    ss = value[4:6]
    fraction = value[6:].strip()
    return f"{hh}:{mm}:{ss}.{fraction}Z" if fraction else f"{hh}:{mm}:{ss}Z"


def format_garmin_datetime(date_text: str, time_text: str) -> str | None:
    if len(date_text) != 6 or len(time_text) < 6 or not (date_text + time_text[:6]).isdigit():
        return None
    year = int(date_text[0:2])
    month = date_text[2:4]
    day = date_text[4:6]
    full_year = 2000 + year if year < 80 else 1900 + year
    return f"{full_year:04d}-{month}-{day}T{time_text[0:2]}:{time_text[2:4]}:{time_text[4:6]}Z"


def parse_garmin_lat_lon(value: str) -> float | None:
    if len(value) < 4:
        return None
    hemisphere = value[0]
    digits = value[1:]
    if not digits.isdigit():
        return None
    if hemisphere in {"N", "S"} and len(digits) == 7:
        degrees = int(digits[0:2])
        minutes = int(digits[2:]) / 1000.0
    elif hemisphere in {"E", "W"} and len(digits) == 8:
        degrees = int(digits[0:3])
        minutes = int(digits[3:]) / 1000.0
    else:
        return None
    decimal = degrees + minutes / 60.0
    return -decimal if hemisphere in {"S", "W"} else decimal


GARMIN_EIS_VALUE_PATTERN = re.compile(r"([0-9A-F]{2})([+-]\d\.\d{4}E[+-]\d{2})")


def parse_garmin_text_line(line: str) -> Dict[str, Any] | None:
    stripped = line.strip()
    if not stripped:
        return None

    if stripped.startswith("@") and len(stripped) >= 55:
        latitude_deg = parse_garmin_lat_lon(stripped[13:21])
        longitude_deg = parse_garmin_lat_lon(stripped[21:30])

        gps_horizontal_error_m = parse_int_field(stripped[31:34])
        altitude_m = parse_int_field(stripped[34:40])

        ew_dir = stripped[40]
        ew_speed_mps = parse_int_field(stripped[41:45], scale=10.0)

        ns_dir = stripped[45]
        ns_speed_mps = parse_int_field(stripped[46:50], scale=10.0)

        vertical_dir = stripped[50]
        vertical_speed_mps_raw = parse_int_field(stripped[51:55], scale=100.0)

        east_mps = None
        if ew_speed_mps is not None and ew_dir in {"E", "W"}:
            east_mps = ew_speed_mps if ew_dir == "E" else -ew_speed_mps

        north_mps = None
        if ns_speed_mps is not None and ns_dir in {"N", "S"}:
            north_mps = ns_speed_mps if ns_dir == "N" else -ns_speed_mps

        gps_vertical_velocity_mps = None
        if vertical_speed_mps_raw is not None and vertical_dir in {"U", "D"}:
            gps_vertical_velocity_mps = vertical_speed_mps_raw if vertical_dir == "U" else -vertical_speed_mps_raw

        gps_ground_speed_kt = None
        gps_track_deg = None
        if east_mps is not None and north_mps is not None:
            gps_ground_speed_kt = math.hypot(east_mps, north_mps) * 1.943844492
            gps_track_deg = (math.degrees(math.atan2(east_mps, north_mps)) + 360.0) % 360.0

        row = {
            "garmin_record_type": "@",
            "raw_serial_line": stripped,
            "utc_time": format_garmin_datetime(stripped[1:7], stripped[7:13]),
            "latitude_deg": latitude_deg,
            "longitude_deg": longitude_deg,
            "gps_position_status": stripped[30],
            "gps_horizontal_error_m": gps_horizontal_error_m,
            "gps_altitude_ft": None if altitude_m is None else altitude_m * 3.280839895,
            "gps_ground_speed_kt": gps_ground_speed_kt,
            "gps_track_deg": gps_track_deg,
            "gps_vertical_velocity_mps": gps_vertical_velocity_mps,
            "garmin_gps_altitude_m_raw_field": stripped[34:40],
            "garmin_gps_ew_velocity_raw_field": stripped[40:45],
            "garmin_gps_ns_velocity_raw_field": stripped[45:50],
            "garmin_gps_vertical_velocity_raw_field": stripped[50:55],
        }

        clear_stale_fields = []

        if latitude_deg is None:
            clear_stale_fields.append("latitude_deg")
        if longitude_deg is None:
            clear_stale_fields.append("longitude_deg")
        if altitude_m is None:
            clear_stale_fields.append("gps_altitude_ft")
        if east_mps is None or north_mps is None:
            clear_stale_fields.append("gps_ground_speed_kt")
            clear_stale_fields.append("gps_track_deg")
        if gps_vertical_velocity_mps is None:
            clear_stale_fields.append("gps_vertical_velocity_mps")

        row["_clear_stale_fields"] = clear_stale_fields
        return row

    if stripped.startswith("=1") and len(stripped) >= 57:
        row = {
            "garmin_record_type": "=1",
            "raw_serial_line": stripped,
            "utc_time": format_garmin_time(stripped[3:11]),
            "pitch_deg": parse_int_field(stripped[11:15], scale=10.0),
            "roll_deg": parse_int_field(stripped[15:20], scale=10.0),
            "heading_deg": parse_int_field(stripped[20:23]),
            "ias_kt": parse_int_field(stripped[23:27], scale=10.0),
            "garmin_ias_raw_field": stripped[23:27],
            "pressure_altitude_ft": parse_int_field(stripped[27:33]),
            "rate_of_turn_deg_s": parse_int_field(stripped[33:37], scale=10.0),
            "lateral_acceleration_g": parse_int_field(stripped[37:40], scale=100.0),
            "normal_acceleration_g": parse_int_field(stripped[40:43], scale=10.0),
            "aoa_raw": stripped[43:45],
            "vertical_speed_fpm": multiply_if_present(parse_int_field(stripped[45:49]), 10.0),
            "oat_deg_c": parse_int_field(stripped[49:52]),
            "baro_in_hg": parse_baro_in_hg(stripped[52:55]),
            "garmin_checksum": stripped[55:57],
        }
        field_slices = {
            "pitch_deg": stripped[11:15],
            "roll_deg": stripped[15:20],
            "heading_deg": stripped[20:23],
            "ias_kt": stripped[23:27],
            "pressure_altitude_ft": stripped[27:33],
            "rate_of_turn_deg_s": stripped[33:37],
            "lateral_acceleration_g": stripped[37:40],
            "normal_acceleration_g": stripped[40:43],
            "vertical_speed_fpm": stripped[45:49],
            "oat_deg_c": stripped[49:52],
            "baro_in_hg": stripped[52:55],
        }
        row["_clear_stale_fields"] = [field for field, text in field_slices.items() if invalid_numeric_field(text)]
        return row

    if stripped.startswith("=3") and len(stripped) >= 57:
        row = {
            "garmin_record_type": "=3",
            "raw_serial_line": stripped,
            "utc_time": format_garmin_time(stripped[3:11]),
            "oil_pressure": parse_int_field(stripped[11:14]),
            "oil_temp": parse_int_field(stripped[14:18]),
            "rpm": parse_int_field(stripped[18:22]),
            "garmin_rpm_raw_field": stripped[18:22],
            "manifold_pressure_in_hg": parse_int_field(stripped[26:29], scale=10.0),
            "fuel_flow_gph": parse_int_field(stripped[29:32], scale=10.0),
            "fuel_pressure_psi": parse_int_field(stripped[35:38], scale=10.0),
            "fuel_quantity_1_gal": parse_int_field(stripped[38:41], scale=10.0),
            "fuel_quantity_2_gal": parse_int_field(stripped[41:44], scale=10.0),
            "fuel_remaining_gal": parse_int_field(stripped[44:47], scale=10.0),
            "volts_1": parse_int_field(stripped[47:50], scale=10.0),
            "volts_2": parse_int_field(stripped[50:53], scale=10.0),
            "amps_1": parse_int_field(stripped[53:57], scale=10.0),
        }
        field_slices = {
            "oil_pressure": stripped[11:14],
            "oil_temp": stripped[14:18],
            "rpm": stripped[18:22],
            "manifold_pressure_in_hg": stripped[26:29],
            "fuel_flow_gph": stripped[29:32],
            "fuel_pressure_psi": stripped[35:38],
            "fuel_quantity_1_gal": stripped[38:41],
            "fuel_quantity_2_gal": stripped[41:44],
            "fuel_remaining_gal": stripped[44:47],
            "volts_1": stripped[47:50],
            "volts_2": stripped[50:53],
            "amps_1": stripped[53:57],
        }
        row["_clear_stale_fields"] = [field for field, text in field_slices.items() if invalid_numeric_field(text)]
        return row

    if stripped.startswith("=5"):
        row: Dict[str, Any] = {
            "garmin_record_type": "=5",
            "raw_serial_line": stripped,
            "utc_time": format_garmin_time(stripped[4:12]) if len(stripped) >= 12 else None,
        }
        eis_values: Dict[str, float] = {}
        for sensor_id, value_text in GARMIN_EIS_VALUE_PATTERN.findall(stripped):
            try:
                eis_values[sensor_id] = float(value_text)
            except ValueError:
                continue
        if eis_values:
            row["garmin_eis_values"] = eis_values
        return row

    if stripped.startswith("="):
        return {"raw_serial_line": stripped}

    return None


def parse_line(
    line: str,
    line_format: str,
    csv_fields: Sequence[str],
    learned_header: Sequence[str] | None,
) -> tuple[Dict[str, Any] | None, Sequence[str] | None, str | None]:
    stripped = line.strip()
    if not stripped:
        return None, learned_header, "blank_line"

    selected_format = line_format
    if selected_format == "auto":
        if stripped.startswith("{"):
            selected_format = "json"
        elif stripped.startswith("=") or stripped.startswith("@"):
            selected_format = "garmin-text"
        else:
            selected_format = "csv"

    if selected_format == "raw":
        return {"raw_serial_line": stripped}, learned_header, None

    if selected_format == "garmin-text":
        parsed = parse_garmin_text_line(stripped)
        if parsed is None:
            return None, learned_header, "garmin_text_parse_error"
        return parsed, learned_header, None

    if selected_format == "json":
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return None, learned_header, f"json_parse_error:{exc.msg}"
        if not isinstance(parsed, dict):
            return None, learned_header, "json_line_is_not_object"
        return dict(parsed), learned_header, None

    try:
        cells = parse_csv_line(stripped)
    except csv.Error as exc:
        return None, learned_header, f"csv_parse_error:{exc}"

    if learned_header is None and looks_like_csv_header(cells):
        return None, [cell.strip() for cell in cells], "learned_csv_header"

    header = learned_header or csv_fields
    row = {header[index]: cells[index].strip() for index in range(min(len(header), len(cells)))}
    if len(cells) > len(header):
        for index, value in enumerate(cells[len(header) :], start=len(header)):
            row[f"extra_{index:03d}"] = value.strip()
    return row, learned_header, None


def packet_log_row(
    sequence: int,
    udp_host: str,
    udp_port: int,
    serial_port: str,
    payload: Mapping[str, Any],
    payload_bytes: bytes,
) -> Dict[str, Any]:
    return {
        "sent_wall_time_s": f"{time.time():.6f}",
        "sequence": sequence,
        "serial_port": serial_port,
        "udp_host": udp_host,
        "udp_port": udp_port,
        "utc_time": payload.get("utc_time") or "",
        "ias_kt": payload.get("ias_kt") if payload.get("ias_kt") is not None else "",
        "pitch_deg": payload.get("pitch_deg") if payload.get("pitch_deg") is not None else "",
        "roll_deg": payload.get("roll_deg") if payload.get("roll_deg") is not None else "",
        "rpm": payload.get("rpm") if payload.get("rpm") is not None else "",
        "payload_bytes": len(payload_bytes),
        "payload_json": payload_bytes.decode("utf-8"),
    }


def short_text(value: str | None, limit: int = 180) -> str:
    if value is None:
        return ""
    text = value.replace("\r", "\\r").replace("\n", "\\n")
    text = text.encode("ascii", errors="backslashreplace").decode("ascii")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def format_live_value(value: Any, digits: int = 1) -> str:
    if value is None:
        return "--"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "--"
    return f"{number:.{digits}f}"


def print_live_packet(sequence: int, payload: Mapping[str, Any], raw_line: str | None, show_raw: bool) -> None:
    print(
        "packet "
        f"{sequence} "
        f"IAS={format_live_value(payload.get('ias_kt'))} "
        f"pitch={format_live_value(payload.get('pitch_deg'))} "
        f"roll={format_live_value(payload.get('roll_deg'))} "
        f"RPM={format_live_value(payload.get('rpm'), digits=0)} "
        f"bytes={len(json.dumps(payload, separators=(',', ':'), allow_nan=False).encode('utf-8'))}"
    )
    if show_raw:
        print(f"  raw={short_text(raw_line)}")


def list_serial_ports() -> None:
    list_ports = import_list_ports()
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    for port in ports:
        print(f"{port.device}: {port.description} [{port.hwid}]")


def serial_lines(port: str, baud: int, timeout: float) -> Iterable[str]:
    serial = import_serial()
    with serial.Serial(port=port, baudrate=baud, timeout=timeout) as handle:
        print(f"Opened {port} at {baud} baud")
        while True:
            raw = handle.readline()
            if not raw:
                continue
            yield raw.decode("utf-8", errors="replace").strip()


def monitor_serial_bytes(port: str, baud: int, timeout: float, chunk_size: int, max_chunks: int | None) -> None:
    serial = import_serial()
    with serial.Serial(port=port, baudrate=baud, timeout=timeout) as handle:
        print(f"Opened {port} at {baud} baud for byte monitor")
        print("Press Ctrl+C to stop.")
        chunks = 0
        try:
            while True:
                raw = handle.read(max(chunk_size, 1))
                if not raw:
                    continue
                hex_text = " ".join(f"{byte:02X}" for byte in raw)
                ascii_text = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in raw)
                print(f"{time.time():.3f} bytes={len(raw)} hex={hex_text} ascii={ascii_text}")
                chunks += 1
                if max_chunks is not None and chunks >= max_chunks:
                    return
        except KeyboardInterrupt:
            print("Interrupted")


def read_byte(handle: Any) -> int | None:
    value = handle.read(1)
    if not value:
        return None
    return value[0]


def read_garmin_dle_packet(handle: Any) -> bytes | None:
    # Garmin binary packets are commonly framed as:
    # DLE, packet_id, payload_size, payload..., checksum, DLE, ETX.
    # Any literal DLE byte inside the packet body is escaped as DLE DLE.
    while True:
        byte = read_byte(handle)
        if byte is None:
            return None
        if byte == 0x10:
            break

    content = bytearray()
    while True:
        byte = read_byte(handle)
        if byte is None:
            return None
        if byte != 0x10:
            content.append(byte)
            continue

        next_byte = read_byte(handle)
        if next_byte is None:
            return None
        if next_byte == 0x10:
            content.append(0x10)
            continue
        if next_byte == 0x03:
            return bytes(content)

        # Not an escaped DLE or terminator. Treat this as a lost sync and
        # restart from the new DLE candidate.
        content.clear()
        if next_byte != 0x10:
            content.append(next_byte)


def monitor_garmin_binary(port: str, baud: int, timeout: float, max_packets: int | None) -> None:
    serial = import_serial()
    with serial.Serial(port=port, baudrate=baud, timeout=timeout) as handle:
        print(f"Opened {port} at {baud} baud for Garmin DLE packet monitor")
        print("Press Ctrl+C to stop.")
        packets = 0
        try:
            while True:
                packet = read_garmin_dle_packet(handle)
                if packet is None:
                    continue
                packets += 1
                packet_id = packet[0] if len(packet) >= 1 else None
                payload_size = packet[1] if len(packet) >= 2 else None
                payload = packet[2:-1] if len(packet) >= 3 else b""
                checksum = packet[-1] if packet else None
                checksum_valid = bool(packet) and (sum(packet) & 0xFF) == 0
                size_valid = payload_size is not None and payload_size == len(payload)
                payload_hex = " ".join(f"{byte:02X}" for byte in payload)
                decoded_hint = ""
                if len(payload) == 2:
                    unsigned = int.from_bytes(payload, byteorder="little", signed=False)
                    signed = int.from_bytes(payload, byteorder="little", signed=True)
                    decoded_hint = f" u16le={unsigned} s16le={signed}"
                print(
                    f"{time.time():.3f} packet={packets} "
                    f"id=0x{packet_id:02X}({packet_id}) size={payload_size} "
                    f"payload_len={len(payload)} checksum=0x{checksum:02X} "
                    f"checksum_ok={checksum_valid} size_ok={size_valid} "
                    f"payload={payload_hex}{decoded_hint}"
                )
                if max_packets is not None and packets >= max_packets:
                    return
        except KeyboardInterrupt:
            print("Interrupted")


def stdin_lines() -> Iterable[str]:
    for line in sys.stdin:
        yield line.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge laptop RS-232 serial telemetry to Android UDP JSON telemetry.")
    parser.add_argument("--list-ports", action="store_true", help="List Windows COM ports and exit.")
    parser.add_argument("--port", help="Serial port, e.g. COM10. Required unless --stdin or --list-ports is used.")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate. Garmin RS-232 is often 9600.")
    parser.add_argument("--timeout", type=float, default=1.0, help="Serial read timeout in seconds.")
    parser.add_argument("--stdin", action="store_true", help="Read telemetry lines from stdin instead of a COM port.")
    parser.add_argument("--udp-host", help="Phone IP address or subnet broadcast address.")
    parser.add_argument("--udp-port", type=int, default=49005)
    parser.add_argument("--broadcast", action="store_true", help="Enable SO_BROADCAST explicitly.")
    parser.add_argument("--line-format", choices=("auto", "csv", "json", "raw", "garmin-text"), default="auto")
    parser.add_argument(
        "--csv-fields",
        default=",".join(DEFAULT_CSV_FIELDS),
        help="Comma-separated field names for CSV serial lines that do not include a header.",
    )
    parser.add_argument("--log", default="outputs/garmin_rs232_udp_packets.csv", help="CSV log of every sent packet.")
    parser.add_argument("--max-packets", type=int, default=None, help="Optional bench-test limit.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and log packets without sending UDP.")
    parser.add_argument("--print-packets", action="store_true", help="Print decoded live packets to the laptop console.")
    parser.add_argument("--print-raw", action="store_true", help="With --print-packets, also print the raw serial line.")
    parser.add_argument("--print-skipped", action="store_true", help="Print skipped/undecodable serial lines.")
    parser.add_argument("--monitor-bytes", action="store_true", help="Do not send UDP; print raw serial bytes as hex/ascii.")
    parser.add_argument("--monitor-chunk-size", type=int, default=64, help="Bytes per read for --monitor-bytes.")
    parser.add_argument("--monitor-garmin-binary", action="store_true", help="Do not send UDP; parse Garmin DLE-framed binary packets.")
    args = parser.parse_args()

    if args.list_ports:
        list_serial_ports()
        return

    if not args.stdin and not args.port:
        raise SystemExit("Missing --port. Use --list-ports to find COM ports, or --stdin for a parser bench test.")
    if args.monitor_bytes:
        monitor_serial_bytes(str(args.port), int(args.baud), float(args.timeout), int(args.monitor_chunk_size), args.max_packets)
        return
    if args.monitor_garmin_binary:
        monitor_garmin_binary(str(args.port), int(args.baud), float(args.timeout), args.max_packets)
        return
    if not args.udp_host:
        raise SystemExit("Missing --udp-host. Use the phone IP shown in the Android telemetry panel.")

    csv_fields = parse_csv_fields(args.csv_fields)
    log_path = repo_path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fields = [
        "sent_wall_time_s",
        "sequence",
        "serial_port",
        "udp_host",
        "udp_port",
        "utc_time",
        "ias_kt",
        "pitch_deg",
        "roll_deg",
        "rpm",
        "payload_bytes",
        "payload_json",
    ]

    source_name = "garmin_rs232_stdin" if args.stdin else "garmin_rs232_bridge"
    serial_name = "stdin" if args.stdin else str(args.port)
    line_source = stdin_lines() if args.stdin else serial_lines(str(args.port), int(args.baud), float(args.timeout))

    print(f"Forwarding {serial_name} telemetry to {args.udp_host}:{args.udp_port}")
    print(f"Line format: {args.line_format}")
    print(f"Packet log: {log_path}")
    if args.print_packets:
        print("Live packet print enabled")
    if args.dry_run:
        print("Dry run: UDP send disabled")

    sent = 0
    sequence = 0
    learned_header: Sequence[str] | None = None
    latest_values: Dict[str, Any] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        if should_enable_broadcast(str(args.udp_host), args.broadcast):
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        with open(log_path, "w", encoding="utf-8", newline="") as log_handle:
            writer = csv.DictWriter(log_handle, fieldnames=log_fields, lineterminator="\n")
            writer.writeheader()
            try:
                for line in line_source:
                    row, learned_header, skip_reason = parse_line(line, args.line_format, csv_fields, learned_header)
                    if row is None:
                        if skip_reason and skip_reason != "blank_line" and (args.print_skipped or skip_reason == "learned_csv_header"):
                            print(f"Skipped line: {skip_reason} raw={short_text(line)}")
                        continue
                    clear_stale_fields = set(row.get("_clear_stale_fields", ()))
                    for field in clear_stale_fields:
                        latest_values.pop(field, None)
                    payload = build_payload(row, sequence, source=source_name, raw_line=line)
                    for field in TELEMETRY_FIELDS:
                        if field in clear_stale_fields:
                            payload[field] = None
                        elif payload.get(field) is None and field in latest_values:
                            payload[field] = latest_values[field]
                        elif payload.get(field) is not None:
                            latest_values[field] = payload[field]
                    payload_bytes = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
                    if not args.dry_run:
                        udp_socket.sendto(payload_bytes, (str(args.udp_host), int(args.udp_port)))
                    writer.writerow(
                        packet_log_row(sequence, str(args.udp_host), int(args.udp_port), serial_name, payload, payload_bytes)
                    )
                    log_handle.flush()
                    if args.print_packets:
                        print_live_packet(sequence, payload, line, args.print_raw)
                    sent += 1
                    sequence += 1
                    if args.max_packets is not None and sent >= args.max_packets:
                        print(f"Sent {sent} packets")
                        return
            except KeyboardInterrupt:
                print("Interrupted")

    print(f"Sent {sent} packets")


if __name__ == "__main__":
    main()
