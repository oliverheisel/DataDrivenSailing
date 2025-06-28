import threading
import time
from smbus2 import SMBus
import logging
from config import config

# initialize logger for this module
logger = logging.getLogger(__name__)

# max17048 i2c address
I2C_BUS = 1
MAX17048_ADDRESS = 0x36

# register addresses for battery voltage and percentage
VCELL_REGISTER = 0x02  # battery voltage register
SOC_REGISTER = 0x04    # battery percentage register

# battery status variables
battery_voltage = 0.0
battery_percentage = 0.0

# initialize i2c bus
i2c = SMBus(I2C_BUS)

def read_battery():
    """
    reads battery voltage and percentage from max17048 over i2c.
    updates global variables for battery monitoring.
    """
    global battery_voltage, battery_percentage

    while True:
        try:
            # read raw register data (2 bytes per register)
            raw_voltage = i2c.read_word_data(MAX17048_ADDRESS, VCELL_REGISTER)
            raw_percent = i2c.read_word_data(MAX17048_ADDRESS, SOC_REGISTER)

            # swap byte order (fix for raspberry pi)
            voltage_swapped = ((raw_voltage << 8) & 0xFF00) | (raw_voltage >> 8)
            percent_swapped = ((raw_percent << 8) & 0xFF00) | (raw_percent >> 8)

            # convert raw data to readable values
            battery_voltage = round(voltage_swapped * 78.125 / 1_000_000, 2)  # convert to volts
            battery_percentage = round(percent_swapped / 256.0, 1)            # convert to percentage

        except OSError as e:
            # log error if reading battery data fails
            logger.error("battery_read_battery_error reading battery data: %s. check i2c connection.", e)
            battery_voltage, battery_percentage = 0.0, 0.0

        # wait one second before next reading
        time.sleep(1)

# start battery monitoring thread as a daemon
if config.device_type != "hub":
    battery_thread = threading.Thread(target=read_battery, daemon=True)
    battery_thread.start()

def get_battery_json():
    return {
        "batvolt": battery_voltage,  # now a float
        "batperc": battery_percentage  # now a float
    }
