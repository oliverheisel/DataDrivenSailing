#!/usr/bin/env python3
"""
GPS driver for u-blox SAM-M10Q on I²C

Adds:
  • NMEA checksum validation
  • Jump rejection – fixes that imply an impossible speed are discarded
"""

from __future__ import annotations
import time, math, re, logging
from smbus2 import SMBus, i2c_msg
from config import config

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Configurable constants                                                      #
# --------------------------------------------------------------------------- #
DEVICE_ADDRESS     = int(config.gps_i2c, 16)
MAX_SPEED_KNOTS    = getattr(config, "GPS_MAX_SPEED_KNOTS", 25)   # physical cap
MAX_SPEED_MPS      = MAX_SPEED_KNOTS * 0.514444
I2C_READ_LEN       = 64                          # bytes per transfer

# --------------------------------------------------------------------------- #
# Predefined UBX rate config commands                                         #
# --------------------------------------------------------------------------- #
cfg1 = [
    0xB5,0x62, 0x06,0x8A, 0x0A,0x00, 0x01,0x01,0x00,0x00,
    0x01,0x00,0x21,0x30, 0x01,0x00, 0x00,0x00
]

cfg2 = [
    0xB5,0x62, 0x06,0x8A, 0x0A,0x00, 0x01,0x01,0x00,0x00,
    0x01,0x00,0x21,0x30, 0x02,0x00, 0x00,0x00
]

cfg5 = [
    0xB5,0x62, 0x06,0x8A, 0x0A,0x00, 0x01,0x01,0x00,0x00,
    0x01,0x00,0x21,0x30, 0x05,0x00, 0x00,0x00
]

cfg10 = [
    0xB5, 0x62, 0x06, 0x8A, 0x0A, 0x00,0x01, 0x01, 0x00, 0x00,
    0x01, 0x00, 0x21, 0x30, 0x64, 0x00, 0x52, 0xC3
]

cfg15 = [
    0xB5,0x62, 0x06,0x8A, 0x0A,0x00, 0x01,0x01,0x00,0x00,
    0x01,0x00,0x21,0x30, 0x15,0x00, 0x00,0x00
]

cfg20 = [
    0xB5,0x62, 0x06,0x8A, 0x0A,0x00, 0x01,0x01,0x00,0x00,
    0x01,0x00,0x21,0x30, 0x20,0x00, 0x00,0x00
]

cfg25 = [
    0xB5,0x62, 0x06,0x8A, 0x0A,0x00, 0x01,0x01,0x00,0x00,
    0x01,0x00,0x21,0x30, 0x25,0x00, 0x00,0x00
]

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _nmea_checksum_ok(sentence: str) -> bool:
    """Return True if the trailing *hh checksum is correct."""
    if not (sentence.startswith("$") and "*" in sentence):
        return False
    body, cks = sentence[1:].split("*", 1)
    try:
        want = int(cks[:2], 16)
    except ValueError:
        return False
    got = 0
    for ch in body:
        got ^= ord(ch)
    return got == want

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in metres."""
    R = 6371000.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ     = φ2 - φ1
    dλ     = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# --------------------------------------------------------------------------- #
# Sentence → decimal helpers                                                  #
# --------------------------------------------------------------------------- #
def _to_decimal(value: str, direction: str, is_lat: bool):
    if not value:
        return None
    numeric_part = re.search(r"[\d.]+", value)
    if not numeric_part:
        return None
    v = numeric_part.group(0)
    if is_lat:
        deg, minutes = int(v[:2]), float(v[2:])
    else:
        deg, minutes = int(v[:3]), float(v[3:])
    dec = deg + minutes / 60.0
    if direction in ("S", "W"):
        dec = -dec
    return round(dec, 8)

# --------------------------------------------------------------------------- #
# Module-level state                                                          #
# --------------------------------------------------------------------------- #
_default = dict.fromkeys(
    ["datetime","status","lat","long","SOG","COG","fixQ","nSat","HDOP","alt"]
)
_data           = _default.copy()
_buffer         = ""
_prev_lat       = None
_prev_lon       = None
_prev_time_utc  = None            # float seconds since epoch

i2c_bus = SMBus(1)

# --------------------------------------------------------------------------- #
# NMEA parsing                                                                #
# --------------------------------------------------------------------------- #
def _parse(line: str) -> None:
    """Update the module-level _data dict from one NMEA sentence."""
    global _data, _prev_lat, _prev_lon, _prev_time_utc

    # ── discard corrupted sentences ───────────────────────────────────────────
    if not _nmea_checksum_ok(line):
        return

    f = line.split(",")

    # ── Recommended Minimum data (date, time, status, pos, SOG/COG) ──────────
    if line.startswith("$GNRMC"):
        status = f[2] if len(f) > 2 else None
        _data["status"] = status

        # ---- datetime is present even when status == "V" --------------------
        try:
            date_str, time_utc = f[9], f[1]                   # ddmmyy, hhmmss.ss
            if date_str and time_utc and len(date_str) >= 6 and len(time_utc) >= 6:
                y = f"20{date_str[4:6]}";  m = date_str[2:4];  d = date_str[:2]
                hh, mm, ss = time_utc[:2], time_utc[2:4], time_utc[4:]
                _data["datetime"] = f"{y}-{m}-{d}T{hh}:{mm}:{float(ss):05.2f}Z"
        except Exception:
            _data["datetime"] = None

        # speed over ground / course over ground
        _data["SOG"] = float(f[7]) if f[7] else None
        _data["COG"] = float(f[8]) if f[8] else None

        # no valid position yet → keep the time but clear coords & return
        if status != "A":
            _data["lat"] = _data["long"] = _data["alt"] = None
            return

        # ---- convert position ------------------------------------------------
        lat = _to_decimal(f[3], f[4], True)
        lon = _to_decimal(f[5], f[6], False)
        if lat is None or lon is None:
            return

        # ---- jump-rejection against impossible speed ------------------------
        if _prev_lat is not None:
            dt = time.time() - _prev_time_utc
            dist_m = _haversine_m(_prev_lat, _prev_lon, lat, lon)
            if dt > 0 and dist_m / dt > MAX_SPEED_MPS:
                logger.warning("GPS spike rejected: %.1f m in %.2f s = %.1f m/s",
                               dist_m, dt, dist_m / dt)
                return
        _prev_lat, _prev_lon, _prev_time_utc = lat, lon, time.time()

        _data["lat"], _data["long"] = lat, lon
        sog = float(f[7]) if f[7] else None
        cog = float(f[8]) if f[8] else None
        _data["SOG"] = sog
        _data["COG"] = cog if sog is None or sog >= 0.5 else None

    # ── Fix data (quality, sats, HDOP, altitude) ─────────────────────────────
    elif line.startswith("$GNGGA"):
        _data["fixQ"] = int(f[6]) if f[6].isdigit() else None
        _data["nSat"] = int(f[7]) if f[7].isdigit() else None
        _data["HDOP"] = float(f[8]) if f[8] else None
        _data["alt"]  = float(f[9]) if f[9] else None


# --------------------------------------------------------------------------- #
# I²C reader thread                                                           #
# --------------------------------------------------------------------------- #
def read_gps() -> None:
    global _buffer
    while True:
        try:
            msg = i2c_msg.read(DEVICE_ADDRESS, I2C_READ_LEN)
            i2c_bus.i2c_rdwr(msg)
            _buffer += "".join(
                chr(b) for b in msg if b in (10,13) or 32 <= b <= 126
            )

            while True:
                nl = _buffer.find("\n")
                if nl == -1:
                    break
                line = _buffer[:nl].rstrip("\r")
                _buffer = _buffer[nl+1:]
                if line.startswith(("$GN", "$GP", "$GA")):
                    _parse(line)
        except OSError as e:
            logger.error("GPS I2C error: %s", e)
        time.sleep(0.05)

# --------------------------------------------------------------------------- #
# Public helpers                                                              #
# --------------------------------------------------------------------------- #
def get_data():
    return _data.copy()

def init_gps():
    """Configures the GPS update rate based on config.GPS_UPDATE_HZ."""
    rate = getattr(config, "GPS_UPDATE", 10)
    configs = {
        1:  cfg1,
        2:  cfg2,
        5:  cfg5,
        10: cfg10,
        15: cfg15,
        20: cfg20,
        25: cfg25
    }
    cfg = configs.get(rate, cfg10)
    if cfg is cfg10 and rate != 10:
        logger.warning("Unsupported GPS rate '%s Hz'; using 10 Hz fallback", rate)

    try:
        with SMBus(1) as bus:
            bus.write_i2c_block_data(DEVICE_ADDRESS, 0xFF, cfg)
            logger.debug("GPS update rate configured: %d Hz", rate)
    except Exception as e:
        logger.error("GPS init failed: %s", e)

