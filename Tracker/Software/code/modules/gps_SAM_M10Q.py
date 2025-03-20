import time
from smbus2 import SMBus, i2c_msg
from config import config
import logging
import re

# initialize logger for this module
logger = logging.getLogger(__name__)

# convert gps i2c address from string (e.g., "0x42") to integer
DEVICE_ADDRESS = int(config.gps_i2c, 16)

ubx_rate_config = [
    0xB5, 0x62,  # ubx header sync chars
    0x06, 0x8A,  # class = cfg (0x06), id = 0x8a (cfg-valset in u-blox m10)
    0x0A, 0x00,  # payload length = 10 bytes
    0x01, 0x01, 0x00, 0x00,  # part of the cfg-valset payload
    0x01, 0x00, 0x21, 0x30,  # additional payload bytes
    0x64, 0x00,              # additional payload bytes
    0x52, 0xC3               # checksum (ck_a, ck_b)
]

# a dictionary of all desired gps fields, with default None values
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

# module-level variables for gps data and buffer
_buffer_str = ""  # buffer to store incoming gps data
_combined_data = _default_fields.copy()  # mutable copy of gps data

# create an i2c bus object for raspberry pi (bus 1 is common)
i2c_bus = SMBus(1)

def convert_to_decimal(value, direction, is_lat):
    """
    Converts an nmea lat/lon string to decimal degrees.
    Cleans the value string by removing any non-numeric and non-decimal characters.
    """
    if not value:
        return None
    try:
        # Extract the numeric portion (digits and dot) from the value string.
        # This will remove trailing characters such as 'N', 'E', or a stray checksum marker.
        numeric_part = re.search(r"[\d.]+", value)
        if not numeric_part:
            raise ValueError(f"Unable to extract numeric part from {value}")
        value_clean = numeric_part.group(0)

        if is_lat:
            # For latitude, first two digits represent degrees.
            deg = int(value_clean[:2])
            minutes = float(value_clean[2:])
        else:
            # For longitude, first three digits represent degrees.
            deg = int(value_clean[:3])
            minutes = float(value_clean[3:])
        decimal_degrees = deg + (minutes / 60.0)
        if direction in ('S', 'W'):
            decimal_degrees = -decimal_degrees
        return round(decimal_degrees, 8)
    except ValueError as e:
        logger.error("gps_convert_to_decimal_error: %s", e)
        return None

def parse_nmea_line(line):
    """
    parses an nmea sentence and updates the global gps data dictionary.
    ensures numerical values are correctly converted from strings.
    """
    global _combined_data
    fields = line.split(',')

    # ensure _combined_data has all required keys
    for key in _default_fields:
        _combined_data.setdefault(key, None)

    if line.startswith('$GNRMC'):
        # update status, sog, and cog from rmc sentence
        _combined_data["status"] = fields[2] if len(fields) > 2 else None
        _combined_data["SOG"] = float(fields[7]) if len(fields) > 7 and fields[7].replace('.', '', 1).isdigit() else None
        _combined_data["COG"] = float(fields[8]) if len(fields) > 8 and fields[8].replace('.', '', 1).isdigit() else None

        # convert and update latitude
        raw_lat = fields[3] if len(fields) > 3 else ""
        lat_dir = fields[4] if len(fields) > 4 else ""
        _combined_data["lat"] = convert_to_decimal(raw_lat, lat_dir, is_lat=True)

        # convert and update longitude
        raw_lon = fields[5] if len(fields) > 5 else ""
        lon_dir = fields[6] if len(fields) > 6 else ""
        _combined_data["long"] = convert_to_decimal(raw_lon, lon_dir, is_lat=False)

        # update date and time information
        try:
            date_str = fields[9] if len(fields) > 9 else ""
            time_utc = fields[1] if len(fields) > 1 else ""
            if len(date_str) >= 6 and len(time_utc) >= 6:
                day, month, year = date_str[:2], date_str[2:4], f"20{date_str[4:6]}"
                hours, minutes = int(time_utc[:2]), int(time_utc[2:4])
                seconds = float(time_utc[4:])
                _combined_data["datetime"] = f"{year}-{month}-{day}T{hours:02d}:{minutes:02d}:{seconds:05.2f}Z"
        except Exception as e:
            logger.error("gps_parse_nmea_line_error parsing datetime: %s", e)
            _combined_data["datetime"] = None

    elif line.startswith('$GNGGA'):
        # update fix quality, number of satellites, hdop, and altitude from gga sentence
        _combined_data["fixQ"] = int(fields[6]) if len(fields) > 6 and fields[6].isdigit() else None
        _combined_data["nSat"] = int(fields[7]) if len(fields) > 7 and fields[7].isdigit() else None
        _combined_data["HDOP"] = float(fields[8]) if len(fields) > 8 and fields[8].replace('.', '', 1).isdigit() else None
        _combined_data["alt"] = float(fields[9]) if len(fields) > 9 and fields[9].replace('.', '', 1).isdigit() else None

def read_gps():
    """
    continuously reads data from the gps over i2c and updates the buffer.
    uses i2c_msg to read 64 bytes per transaction.
    """
    global _buffer_str
    while True:
        try:
            read_length = 64  # number of bytes to read per transaction
            msg = i2c_msg.read(DEVICE_ADDRESS, read_length)
            i2c_bus.i2c_rdwr(msg)
            raw_data = list(msg)
            # filter raw bytes to include only valid ascii characters and newline/carriage return characters
            filtered_chars = [chr(b) for b in raw_data if b in (10, 13) or 32 <= b <= 126]
            _buffer_str += "".join(filtered_chars)

            # process complete lines in the buffer
            while True:
                newline_index = _buffer_str.find("\n")
                if newline_index == -1:
                    break
                line = _buffer_str[:newline_index].rstrip("\r")
                _buffer_str = _buffer_str[newline_index + 1:]
                # process lines that start with valid nmea sentence identifiers
                if line.startswith('$GN') or line.startswith('$GP') or line.startswith('$GA'):
                    parse_nmea_line(line)
        except OSError as e:
            logger.error("gps_read_gps_error: %s", e)
        time.sleep(0.1)

def get_data():
    """
    returns the latest parsed gps data as a dictionary.
    ensures that numerical values are correctly formatted.
    """
    return {
        "datetime": _combined_data["datetime"],
        "status": _combined_data["status"],
        "lat": _combined_data["lat"],
        "long": _combined_data["long"],
        "SOG": _combined_data["SOG"],
        "COG": _combined_data["COG"],
        "fixQ": _combined_data["fixQ"],
        "nSat": _combined_data["nSat"],
        "HDOP": _combined_data["HDOP"],
        "alt": _combined_data["alt"]
    }

def init_gps():
    """
    Initializes the GPS module:
      1. Configures the GPS update rate by sending the UBX command.
      2. Starts the background thread for continuous GPS data reading.
    This single function replaces the separate configuration function.
    """
    try:
        with SMBus(1) as bus:
            # Write the UBX command starting at register 0xFF
            bus.write_i2c_block_data(DEVICE_ADDRESS, 0xFF, ubx_rate_config)
            time.sleep(0.2)  # Allow time for configuration to be processed
            logging.debug("gps_init_gps_GPS update rate configuration message sent to GPS.")
    except Exception as e:
        logging.error("gps_init_gps_Error sending GPS configuration message: %s" % e)