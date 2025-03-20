from smbus2 import SMBus  # use smbus for raspberry pi i2c communication
import time
import math
import json
import logging

# initialize logger for this module
logger = logging.getLogger(__name__)

# i2c address & registers for mmc56x3
MMC56X3_I2C_ADDR = 0x30  # default i2c address for mmc5603/5604/5607, etc.
REG_XOUT_0    = 0x00     # starting register for magnetometer data
REG_CONTROL_0 = 0x1B     # control register (trigger measurement)

# setup smbus for raspberry pi (usually bus 1)
bus = SMBus(1)

def load_offsets(filename="/home/globaladmin/code_local/config/mag_offsets.json"):
    """
    loads calibration offsets from a json file.
    if the file is not found or cannot be parsed, returns offsets of 0 for each axis.
    """
    try:
        with open(filename, "r") as f:
            offsets = json.load(f)
        x_offset = offsets.get("X_OFFSET", 0)
        y_offset = offsets.get("Y_OFFSET", 0)
        z_offset = offsets.get("Z_OFFSET", 0)
        logger.debug("mag_load_offsets_loaded magnetometer offsets: X=%.2f uT, Y=%.2f uT, Z=%.2f uT", x_offset, y_offset, z_offset)
        return x_offset, y_offset, z_offset
    except Exception as e:
        logger.error("mag_load_offsets_error: could not load magnetometer offsets (using 0,0,0). error: %s", str(e))
        return 0, 0, 0

# load calibration offsets once when the module is imported
X_OFFSET, Y_OFFSET, Z_OFFSET = load_offsets()

def read_magnet_data():
    """
    triggers a measurement, reads 9 bytes from the sensor, parses the raw 20-bit data,
    converts it to microteslas (uT), and returns a tuple (x, y, z).
    """
    try:
        # trigger measurement by writing to control register
        bus.write_byte_data(MMC56X3_I2C_ADDR, REG_CONTROL_0, 0x01)
        time.sleep(0.002)  # wait for measurement to complete

        # read 9 bytes starting at reg_xout_0
        data = bus.read_i2c_block_data(MMC56X3_I2C_ADDR, REG_XOUT_0, 9)

        # parse raw 20-bit data for each axis
        x_raw = (data[0] << 12) | (data[1] << 4) | (data[6] >> 4)
        y_raw = (data[2] << 12) | (data[3] << 4) | (data[7] >> 4)
        z_raw = (data[4] << 12) | (data[5] << 4) | (data[8] >> 4)

        # convert from unsigned 20-bit to signed (two's complement conversion)
        x_raw -= 1 << 19
        y_raw -= 1 << 19
        z_raw -= 1 << 19

        # scale raw values to microteslas
        x_uT = x_raw * 0.00625
        y_uT = y_raw * 0.00625
        z_uT = z_raw * 0.00625

        #logger.debug("mag_read_magnet_data: X=%.4f uT, Y=%.4f uT, Z=%.4f uT", x_uT, y_uT, z_uT)
        return x_uT, y_uT, z_uT
    except Exception as e:
        logger.error("mag_read_magnet_data_error: %s", str(e))
        return 0.0, 0.0, 0.0

def calculate_heading(x, y):
    """
    calculates the compass heading (in degrees) from the horizontal (x, y) components.
    heading is measured from the positive x-axis toward the positive y-axis.
    """
    angle_rad = math.atan2(-x, y)
    angle_deg = math.degrees(angle_rad)
    if angle_deg < 0:
        angle_deg += 360
    return angle_deg

def get_data():
    """
    reads the magnetometer sensor, applies calibration offsets,
    computes the compass heading, and returns a dictionary with:
      - 'mag_x': corrected x-axis reading (uT)
      - 'mag_y': corrected y-axis reading (uT)
      - 'mag_z': corrected z-axis reading (uT)
      - 'heading': compass heading (degrees)
    the values are rounded to 4 decimal places.
    """
    try:
        # get raw sensor data
        x_raw, y_raw, z_raw = read_magnet_data()

        # apply calibration offsets
        x_corr = x_raw - X_OFFSET
        y_corr = y_raw - Y_OFFSET
        z_corr = z_raw - Z_OFFSET

        # calculate the compass heading using the horizontal components
        heading = calculate_heading(x_corr, y_corr)

        data = {
            "mag_x": round(x_corr, 4),
            "mag_y": round(y_corr, 4),
            "mag_z": round(z_corr, 4),
            "heading": round(heading, 4)
        }
        #logger.debug("mag_get_data: %s", data)
        return data
    except Exception as e:
        logger.error("mag_get_data_error: %s", str(e))
        return {"mag_x": 0.0, "mag_y": 0.0, "mag_z": 0.0, "heading": 0.0}