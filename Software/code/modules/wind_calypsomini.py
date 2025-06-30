"""
Wind Calypso Mini driver — on-demand read (no background thread)

`get_data(heading=0.0)` grabs the newest MWV sentence from the serial
buffer, converts it to a dict, and adds a true-wind direction:
    true_wind_dir = (heading + w_angle) % 360
"""

import serial, time, logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Serial parameters
# ---------------------------------------------------------------------------
_PORT    = "/dev/serial0"
_BAUD    = 38400
_TIMEOUT = 0.05             # s – short to stay non-blocking

_SER: serial.Serial | None = None


def _ensure_serial() -> serial.Serial:
    """Open the port once and keep it open."""
    global _SER
    if _SER and _SER.is_open:
        return _SER
    _SER = serial.Serial(
        _PORT,
        _BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=_TIMEOUT,
    )
    return _SER



# MWV parser
def _parse_mwv(sentence: str) -> dict:
    """
    Parse one $--MWV line.

    Format: $--MWV,ANGLE,R/T,SPEED,UNIT,A/V*hh
    """
    if not (sentence.startswith("$") and "MWV" in sentence):
        raise ValueError("not an MWV sentence")

    try:
        body, _ = sentence.split("*", 1)
        _, angle, _, speed, unit, status = body.split(",", 5)
        return {
            "w_angle": float(angle) if angle else None,
            "w_speed": float(speed) if speed else None,
            "w_unit":  unit.upper(),
            "w_status": status,
        }
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"parse error: {e}") from None



# Public API
_LAST_SAMPLE: dict | None = None
_LAST_TS: float | None = None
_MAX_AGE = 0.25  # s – reuse a sample if it's still fresh


def get_data(heading: float = 0.0) -> dict | None:
    """
    Return the latest wind reading or None if nothing is available.

    - Reads *one* MWV sentence if cached data is older than `_MAX_AGE`.
    - Adds `true_wind_dir`.
    """
    global _LAST_SAMPLE, _LAST_TS

    now = time.monotonic()
    if _LAST_TS and now - _LAST_TS < _MAX_AGE and _LAST_SAMPLE is not None:
        sample = _LAST_SAMPLE.copy()
    else:
        ser = _ensure_serial()

        sample = None  #  DEFAULT so UnboundLocalError can't happen

        # Drain buffer to obtain the most recent line
        while ser.in_waiting:
            line = ser.readline()
            if not line:
                break

            decoded = line.decode(errors="replace").strip()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("wind raw: %s", decoded)

            try:
                sample = _parse_mwv(decoded)
            except ValueError:
                continue  # skip non-MWV or malformed lines

        if sample is None:                 # nothing usable read
            return None

        _LAST_SAMPLE = sample
        _LAST_TS = now

    # true-wind 
    try:
        hdg = float(heading)
        wa = float(sample.get("w_angle", 0))
        sample["true_wind_dir"] = round((hdg + wa) % 360, 2)
    except (ValueError, TypeError):
        sample["true_wind_dir"] = None

    # speed in knots (optional convenience)
    if sample.get("w_speed") is not None and sample.get("w_unit") == "M":
        sample["w_speed_kts"] = sample["w_speed"] * 1.943844

    return sample
