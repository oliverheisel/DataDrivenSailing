import threading
import time
from smbus2 import SMBus

# MAX17048 I2C Address
I2C_BUS = 1
MAX17048_ADDRESS = 0x36

# Register addresses
VCELL_REGISTER = 0x02  # Battery voltage
SOC_REGISTER = 0x04  # Battery percentage

# Battery status variables
battery_voltage = 0.0
battery_percentage = 0.0

# Initialize I2C
i2c = SMBus(I2C_BUS)

def read_battery():
    """
    Reads battery voltage and percentage from MAX17048 over I2C.
    Updates global variables for battery monitoring.
    """
    global battery_voltage, battery_percentage

    while True:
        try:
            # Read raw register data (2 bytes per register)
            raw_voltage = i2c.read_word_data(MAX17048_ADDRESS, VCELL_REGISTER)
            raw_percent = i2c.read_word_data(MAX17048_ADDRESS, SOC_REGISTER)

            # Swap byte order (fix for Raspberry Pi)
            voltage_swapped = ((raw_voltage << 8) & 0xFF00) | (raw_voltage >> 8)
            percent_swapped = ((raw_percent << 8) & 0xFF00) | (raw_percent >> 8)

            # Convert to readable values
            battery_voltage = voltage_swapped * 78.125 / 1_000_000  # Convert to volts
            battery_percentage = percent_swapped / 256.0  # Convert to percentage

        except OSError:
            print("Error reading battery data. Check I2C connection.")
            battery_voltage, battery_percentage = 0.0, 0.0

        time.sleep(1)  # Read battery status every second

# Start battery monitoring thread
battery_thread = threading.Thread(target=read_battery, daemon=True)
battery_thread.start()

def get_battery_json():
    """
    Returns the latest battery data as a dictionary.
    """
    return {
        "batvolt": f"{battery_voltage:.2f}",
        "batperc": f"{battery_percentage:.1f}"
    }
