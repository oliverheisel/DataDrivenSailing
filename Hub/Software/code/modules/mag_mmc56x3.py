from __future__ import annotations
import json, math, time, logging
from typing import Tuple
import imufusion
from smbus2 import SMBus
from config import config
import numpy as np

logger = logging.getLogger(__name__)

# ─────────── I²C‑Register ───────────
MMC56X3_I2C_ADDR = 0x30
REG_XOUT_0       = 0x00
REG_CONTROL_0    = 0x1B

_bus = SMBus(1)

# ─────────── Offsets laden ───────────

def _load_offsets(path: str = "/home/globaladmin/code/config/mag_offsets.json") -> Tuple[float, float, float]:
    try:
        with open(path, "r", encoding="utf-8") as fp:
            d = json.load(fp)
        logger.debug("Mag‑Offsets: %s", d)
        return d.get("X_OFFSET", 0.0), d.get("Y_OFFSET", 0.0), d.get("Z_OFFSET", 0.0)
    except Exception as exc:                           # noqa: BLE001
        logger.error("mag_load_offsets_error: %s – nutze 0‑Offsets", exc)
        return 0.0, 0.0, 0.0

X_OFF, Y_OFF, Z_OFF = _load_offsets()

# ─────────── Orientierungstransform ───────────
# Sensor ist neutral montiert – keine Transform notwendig

def _apply_orientation(x: float, y: float, z: float):
    """Identitätsfunktion – gibt die Rohwerte unverändert zurück."""
    return x, y, z

# ─────────── Rohdaten lesen ───────────

def _read_raw() -> Tuple[float, float, float]:
    # single‑measurement auslösen
    _bus.write_byte_data(MMC56X3_I2C_ADDR, REG_CONTROL_0, 0x01)
    time.sleep(0.002)  # 2 ms für Messung
    d = _bus.read_i2c_block_data(MMC56X3_I2C_ADDR, REG_XOUT_0, 9)

    def _20bit(i: int):
        raw = (d[i] << 12) | (d[i + 1] << 4) | (d[6 + i // 2] >> 4)
        raw -= 1 << 19  # two's complement
        return raw * 0.00625  # µT / LSB

    return _20bit(0), _20bit(2), _20bit(4)

# ─────────── vollständige Tilt‑Kompensation ───────────
# Create a global AHRS instance
_ahrs = imufusion.Ahrs()
#_ahrs.settings = imufusion.Settings()  # optional: tweak settings here

def _tilt_compensate(mx: float, my: float, mz: float, *, pitch_deg: float, roll_deg: float) -> Tuple[float, float]:
    """
    Apply tilt compensation using AHRS by feeding roll/pitch as equivalent accelerometer input.
    This assumes the device is static or you have real accel/gyro data available.
    """

    # Estimate gravity vector from pitch/roll
    pitch_rad = math.radians(pitch_deg)
    roll_rad = math.radians(roll_deg)

    ax = math.sin(pitch_rad)
    ay = -math.sin(roll_rad) * math.cos(pitch_rad)
    az = math.cos(roll_rad) * math.cos(pitch_rad)

    # Dummy gyro input (0 if static), actual accel input, dummy mag input
    gyro = np.array([0.0, 0.0, 0.0])
    accel = np.array([ax, ay, az])
    mag_dummy = np.array([0.0, 0.0, 0.0])  # not needed here

    _ahrs.update(gyro, accel, mag_dummy, 0.01)  # dt = 10 ms

    # Apply rotation to magnetometer using orientation
    q = _ahrs.quaternion
    mxh, myh, _ = q.inverse().rotate([mx, my, mz])
    return mxh, myh




# ─────────── öffentliches API ───────────

def get_data(*, pitch: float, roll: float) -> dict[str, float]:
    """Liefert kompensierte Magnetometer‑Daten + Kurs.

    Rückgabewerte
    -------------
    mag_x / y / z : µT (Boot‑Koordinaten)
    heading       : 0–360 °; 0 ° = Bug zeigt geogr. Nord, + nach Steuerbord
    """

    try:
        mx, my, mz = _read_raw()
    except OSError as exc:
        logger.error("mag_read_error: %s", exc)
        return {}

    # 1) Offsets
    mx -= X_OFF
    my -= Y_OFF
    mz -= Z_OFF

    # 2) Orientierung (identisch)
    mx, my, mz = _apply_orientation(mx, my, mz)

    # 3) Tilt‑Kompensation
    mxh, myh = _tilt_compensate(mx, my, mz, pitch_deg=pitch, roll_deg=roll)

    # 4) Kurs
    heading = (math.degrees(math.atan2(-myh, mxh)) + 360) % 360

    return {
        "mag_x": round(mx, 4),
        "mag_y": round(my, 4),
        "mag_z": round(mz, 4),
        "heading": round(heading, 2),
    }
