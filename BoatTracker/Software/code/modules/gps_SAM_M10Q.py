import time
import threading
from smbus2 import SMBus, i2c_msg
from config import config

# Convert GPS I2C address from string (e.g., "0x42") to integer
DEVICE_ADDRESS = int(config.gps_i2c, 16)

# A dictionary of all desired GPS fields, with default None values
_default_fields = {
    "datetime": None,
    "status": None,
    "lat": None,
    "long": None,
    "SOG": None,
    "COG": None,
    "fixQ": None,
    "nSat": None,
    "HDOP": None,
    "alt": None
}

# Module-level variables
_buffer_str = ""  # Buffer to store incoming GPS data
_combined_data = _default_fields.copy()  # Mutable copy of GPS data

# Create an I2C bus object for Raspberry Pi (bus 1 is common)
i2c_bus = SMBus(1)

def convert_to_decimal(value, direction, is_lat):
    """
    Converts an NMEA lat/lon string to decimal degrees.
    """
    if not value:
        return None
    try:
        if is_lat:
            deg = int(value[:2])  # First 2 digits for latitude
            minutes = float(value[2:])
        else:
            deg = int(value[:3])  # First 3 digits for longitude
            minutes = float(value[3:])
        decimal_degrees = deg + (minutes / 60.0)
        if direction in ('S', 'W'):
            decimal_degrees = -decimal_degrees
        return decimal_degrees
    except ValueError:
        return None

def parse_nmea_line(line):
    """
    Parses an NMEA sentence and updates the global GPS data dictionary.
    """
    global _combined_data
    fields = line.split(',')

    # Ensure _combined_data has all required keys
    for key in _default_fields:
        _combined_data.setdefault(key, None)

    if line.startswith('$GNRMC'):
        # Status, SOG, COG
        _combined_data["status"] = fields[2] if len(fields) > 2 else None
        _combined_data["SOG"] = fields[7] if len(fields) > 7 else None
        _combined_data["COG"] = fields[8] if len(fields) > 8 else None

        # Latitude
        raw_lat = fields[3] if len(fields) > 3 else ""
        lat_dir = fields[4] if len(fields) > 4 else ""
        _combined_data["lat"] = convert_to_decimal(raw_lat, lat_dir, is_lat=True)

        # Longitude
        raw_lon = fields[5] if len(fields) > 5 else ""
        lon_dir = fields[6] if len(fields) > 6 else ""
        _combined_data["long"] = convert_to_decimal(raw_lon, lon_dir, is_lat=False)

        # Date & Time
        try:
            date_str = fields[9] if len(fields) > 9 else ""
            time_utc = fields[1] if len(fields) > 1 else ""
            if len(date_str) >= 6 and len(time_utc) >= 6:
                day, month, year = date_str[:2], date_str[2:4], f"20{date_str[4:6]}"
                hours, minutes = int(time_utc[:2]), int(time_utc[2:4])
                seconds = float(time_utc[4:])
                _combined_data["datetime"] = f"{year}-{month}-{day}T{hours:02d}:{minutes:02d}:{seconds:05.2f}Z"
        except Exception:
            _combined_data["datetime"] = None

    elif line.startswith('$GNGGA'):
        _combined_data["fixQ"] = fields[6] if len(fields) > 6 else None
        _combined_data["nSat"] = fields[7] if len(fields) > 7 else None
        _combined_data["HDOP"] = fields[8] if len(fields) > 8 else None
        _combined_data["alt"] = fields[9] if len(fields) > 9 else None

def read_gps():
    """
    Continuously reads data from the GPS over I2C and updates the buffer.
    Uses i2c_msg to read 64 bytes per transaction.
    """
    global _buffer_str
    while True:
        try:
            read_length = 64  # Number of bytes to read
            msg = i2c_msg.read(DEVICE_ADDRESS, read_length)
            i2c_bus.i2c_rdwr(msg)
            raw_data = list(msg)
            filtered_chars = [
                chr(b) for b in raw_data if b in (10, 13) or 32 <= b <= 126
            ]
            _buffer_str += "".join(filtered_chars)

            # Process complete lines
            while True:
                newline_index = _buffer_str.find("\n")
                if newline_index == -1:
                    break
                line = _buffer_str[:newline_index].rstrip("\r")
                _buffer_str = _buffer_str[newline_index + 1:]
                if line.startswith('$GN') or line.startswith('$GP') or line.startswith('$GA'):
                    parse_nmea_line(line)
        except OSError:
            # Ignore I2C read errors
            pass
        time.sleep(0.1)

def get_data():
    """
    Returns the latest parsed GPS data as a dictionary.
    """
    return dict(_combined_data)