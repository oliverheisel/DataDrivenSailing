import serial
import threading
import time
import logging

# set up logger
logger = logging.getLogger(__name__)

# global variable to hold the latest wind data
_latest_wind_data = None
_wind_data_lock = threading.Lock()

def parse_mwv_sentence(sentence):
    """
    parse an NMEA MWV sentence.
    expected format: $--MWV,x.x,a,x.x,a*hh
    """
    sentence = sentence.strip()
    if not sentence.startswith('$'):
        raise ValueError("sentence does not start with '$'")
    try:
        data_part, checksum = sentence.split('*')
    except ValueError:
        raise ValueError("sentence does not contain a checksum delimiter '*'")
    # remove the starting '$'
    data_part = data_part[1:]
    fields = data_part.split(',')
    if len(fields) < 6:
        raise ValueError("incomplete MWV sentence")
    if "MWV" not in fields[0]:
        raise ValueError("not an MWV sentence")
    
    try:
        wind_angle = float(fields[1])
    except ValueError:
        wind_angle = None
    try:
        wind_speed = float(fields[3])
    except ValueError:
        wind_speed = None
    wind_speed_units = fields[4].upper()  # normalize to uppercase
    status = fields[5]
    
    return {
        "w_angle": wind_angle,
        "w_speed": wind_speed,  # in m/s
        "w_unit": wind_speed_units,
        "w_status": status,
        "w_checksum": checksum
    }

def wind_sensor_loop(port='/dev/serial0', baudrate=38400, timeout=1, stop_event=None):
    """
    continuously reads wind sensor data from the serial port and updates the
    global wind data. designed to be run in its own thread.
    
    :param port: serial port device (default: '/dev/serial0')
    :param baudrate: serial baud rate (default: 38400)
    :param timeout: read timeout in seconds (default: 1)
    :param stop_event: threading.Event used to signal termination.
    """
    global _latest_wind_data
    try:
        with serial.Serial(port,
                           baudrate=baudrate,
                           bytesize=serial.EIGHTBITS,
                           parity=serial.PARITY_NONE,
                           stopbits=serial.STOPBITS_ONE,
                           timeout=timeout) as ser:
            while stop_event is None or not stop_event.is_set():
                line = ser.readline()
                if not line:
                    continue
                decoded_line = line.decode('utf-8', errors='replace').strip()
                if decoded_line.startswith('$') and "MWV" in decoded_line:
                    try:
                        parsed = parse_mwv_sentence(decoded_line)
                        # convert wind speed from m/s to knots if the unit is 'M'
                        if parsed['w_speed'] is not None and parsed['w_unit'] == 'M':
                            parsed['w_speed_kts'] = parsed['w_speed'] * 1.943844
                        else:
                            parsed['w_speed_kts'] = None
                        with _wind_data_lock:
                            _latest_wind_data = parsed
                        #logger.debug("wind_sensor_loop_parsed data: %s", parsed)
                    except ValueError as e:
                        logger.error("wind_sensor_loop_parsing error: %s", str(e))
                time.sleep(0.1)
    except Exception as e:
        logger.error("wind_sensor_loop_serial port error: %s", str(e))

def get_wind_data():
    """
    returns the latest wind sensor data.
    """
    global _latest_wind_data
    with _wind_data_lock:
        return _latest_wind_data
