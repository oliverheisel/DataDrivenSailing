#!/usr/bin/env python3
import time
from smbus2 import SMBus
import logging

# initialize logger for this module
logger = logging.getLogger(__name__)

# i2c address of the sparkfun sam-m10q
DEVICE_ADDRESS = 0x42

# this is the raw ubx message provided for changing the update rate to 10 hz:
# b5 62 06 8a 0a 00 01 01 00 00 01 00 21 30 64 00 52 c3
ubx_rate_config = [
    0xB5, 0x62,  # ubx header sync chars
    0x06, 0x8A,  # class = cfg (0x06), id = 0x8a (cfg-valset in u-blox m10)
    0x0A, 0x00,  # payload length = 10 bytes
    0x01, 0x01, 0x00, 0x00,  # part of the cfg-valset payload
    0x01, 0x00, 0x21, 0x30,  # additional payload bytes
    0x64, 0x00,              # additional payload bytes
    0x52, 0xC3               # checksum (ck_a, ck_b)
]

def configure_gps_rate():
    """
    sends a ubx command to the sam-m10q to set the update rate to 10 hz.
    """
    try:
        # open the i2c bus
        with SMBus(1) as bus:
            # according to sparkfun / u-blox docs:
            #  - the first data byte on i2c is the register pointer (often 0xff)
            #  - the subsequent bytes are the actual ubx message
            #
            # write_i2c_block_data(device_address, register, list_of_bytes)
            # here the register is 0xff for ubx writes over i2c.
            bus.write_i2c_block_data(DEVICE_ADDRESS, 0xFF, ubx_rate_config)

            # give the module a moment to process the configuration
            time.sleep(0.2)

            print("gps_config_configure_gps_rate_configuration message sent to gps")
    except Exception as e:
        print("gps_config_configure_gps_rate_error sending configuration message: %s", e)

if __name__ == "__main__":
    configure_gps_rate()
