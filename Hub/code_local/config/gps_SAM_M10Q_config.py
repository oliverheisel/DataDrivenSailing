#!/usr/bin/env python3
import time
from smbus2 import SMBus
import logging

# initialize logger for this module
logger = logging.getLogger(__name__)

# I2C address of the SparkFun SAM-M10Q
DEVICE_ADDRESS = 0x42

# New UBX command to set the GPS update rate to 10 Hz:
# B5 62 06 8A 0A 00 01 02 00 00 01 00 21 30 C8 00 B7 94
ubx_rate_config = [
    0xB5, 0x62,  # UBX header sync characters
    0x06, 0x8A,  # Class = CFG (0x06), ID = CFG-VALSET (0x8A)
    0x0A, 0x00,  # Payload length = 10 bytes
    0x01, 0x02, 0x00, 0x00,  # Payload bytes (note: changed 0x04 to 0x02)
    0x01, 0x00, 0x21, 0x30,  # Additional payload bytes
    0xC8, 0x00,              # Additional payload bytes
    0xB7, 0x94               # Checksum bytes (ck_a, ck_b)
]

def configure_gps_rate():
    """
    Sends a UBX command to the SAM-M10Q to set the update rate to 10 Hz.
    """
    try:
        # Open the I2C bus (bus number might vary depending on your hardware)
        with SMBus(1) as bus:
            # Write the UBX command starting at register 0xFF
            bus.write_i2c_block_data(DEVICE_ADDRESS, 0xFF, ubx_rate_config)
            # Allow the module time to process the configuration command
            time.sleep(0.2)
            print("GPS update rate configuration message sent to GPS.")
    except Exception as e:
        print("Error sending GPS configuration message: %s" % e)

if __name__ == "__main__":
    configure_gps_rate()
