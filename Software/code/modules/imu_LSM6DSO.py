import smbus2  # use smbus2 for raspberry pi i2c communication
import math
from config import config  # import your config
import logging

# initialize logger for this module
logger = logging.getLogger(__name__)

# i2c address for lsm6dso from config (default address)
LSM6DSO_ADDR = int(config.imu_i2c, 16)

# lsm6dso register addresses
WHO_AM_I   = 0x0F  # who_am_i register
CTRL1_XL   = 0x10  # accelerometer control register
CTRL2_G    = 0x11  # gyroscope control register
OUTX_L_G   = 0x22  # gyroscope x-axis low byte
OUTX_L_A   = 0x28  # accelerometer x-axis low byte

# accelerometer and gyroscope settings
ACCEL_ODR_104HZ = 0x40  # accelerometer output data rate = 104 hz
ACCEL_FS_2G     = 0x00  # full-scale selection = ±2g
GYRO_ODR_104HZ  = 0x40  # gyroscope output data rate = 104 hz
GYRO_FS_250DPS  = 0x00  # full-scale selection = ±250 dps

# globals to handle initialization only once
_bus = None
_initialized = False

def _write_register(register, value):
    """writes a byte to a specific register."""
    global _bus
    _bus.write_byte_data(LSM6DSO_ADDR, register, value)

def _read_registers(start_register, length):
    """reads multiple bytes starting at a specific register."""
    global _bus
    return _bus.read_i2c_block_data(LSM6DSO_ADDR, start_register, length)

def _twos_complement(value, bits):
    """converts a raw register value to signed integer using two's complement."""
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value

def _apply_orientation(ax, ay, az):
    """
    applies orientation correction to accelerometer data.
    2) then apply one of 3 possible orientations from config.device_orientation.
       adjust these transforms as needed for your physical mounting.
    """
    # step 1: 
    new_ax = -ay
    new_ay = ax
    new_az = az

    # step 2: apply orientation-specific transform
    orientation = getattr(config, "device_orientation", 1)
    if orientation == 1:
        # orientation 1: flat (base) => no extra transform
        pass
    elif orientation == 2:
        # orientation 2: the device is glued to the front wall
        # "top is facing backwards," "back is facing down"
        # rotate around x-axis by +90° as an example:
        # standard rotation around x by +90°:
        #   y' = -z,   z' = y
        old_y = new_ay
        old_z = new_az
        new_ay = -old_z
        new_az = old_y
    elif orientation == 3:
        # orientation 3: same as orientation 2, but the top is facing in the opposite direction.
        # approach: do the orientation 2 transform, then rotate 180° around z:
        # (x, y, z) -> (-x, -y, z)
        old_y = new_ay
        old_z = new_az
        new_ay = -old_z
        new_az = old_y
        # rotate 180° around z-axis
        new_ax = -new_ax
        new_ay = -new_ay

    # return final, corrected axes
    return (new_ax, new_ay, new_az)

def _read_sensor_data():
    """
    reads accelerometer and gyroscope data and returns as a dictionary.
    adjust scaling and orientation corrections as needed.
    """
    # read 6 bytes for accelerometer (x, y, z)
    raw_accel = _read_registers(OUTX_L_A, 6)
    # read 6 bytes for gyroscope (x, y, z)
    raw_gyro  = _read_registers(OUTX_L_G, 6)

    # convert raw accelerometer data
    accel_x = round(_twos_complement(raw_accel[0] | (raw_accel[1] << 8), 16) * 0.061 / 1000, 2)
    accel_y = round(_twos_complement(raw_accel[2] | (raw_accel[3] << 8), 16) * 0.061 / 1000, 2)
    accel_z = round(_twos_complement(raw_accel[4] | (raw_accel[5] << 8), 16) * 0.061 / 1000, 2)

    # apply orientation correction to accelerometer data
    corrected_x, corrected_y, corrected_z = _apply_orientation(accel_x, accel_y, accel_z)

    # convert raw gyroscope data
    gyro_x = round(_twos_complement(raw_gyro[0] | (raw_gyro[1] << 8), 16) * 8.75 / 1000, 2)
    gyro_y = round(_twos_complement(raw_gyro[2] | (raw_gyro[3] << 8), 16) * 8.75 / 1000, 2)
    gyro_z = round(_twos_complement(raw_gyro[4] | (raw_gyro[5] << 8), 16) * 8.75 / 1000, 2)

    # compute pitch and roll from corrected accelerometer data as an example
    pitch = round(math.atan2(corrected_y, math.sqrt(corrected_x**2 + corrected_z**2)) * 180 / math.pi, 2)
    roll = round(math.atan2(-corrected_x, corrected_z) * 180 / math.pi, 2)

    data = {
        "acc_x":   corrected_x,
        "acc_y":   corrected_y,
        "acc_z":   corrected_z,
        "gyro_x":  gyro_x,
        "gyro_y":  gyro_y,
        "gyro_z":  gyro_z,
        "pitch":   pitch,
        "roll":    roll
    }

    return data

def init_sensor():
    """
    initializes the lsm6dso sensor (set up the bus, configure registers, etc.).
    called automatically on first get_data() if not already initialized.
    """
    global _bus, _initialized

    if _initialized:
        return

    # initialize i2c bus
    _bus = smbus2.SMBus(1)

    # check who_am_i register
    try:
        who_am_i = _read_registers(WHO_AM_I, 1)[0]
    except OSError as e:
        logger.error("gyroacc_init_sensor_error reading who_am_i: %s", e)
        raise

    if who_am_i != 0x6C:
        logger.error("gyroacc_init_sensor_error: could not detect lsm6dso. who_am_i returned 0x%02X", who_am_i)
        raise RuntimeError(f"could not detect lsm6dso. who_am_i returned 0x{who_am_i:02X}")

    # configure accelerometer
    _write_register(CTRL1_XL, ACCEL_ODR_104HZ | ACCEL_FS_2G)
    # configure gyroscope
    _write_register(CTRL2_G, GYRO_ODR_104HZ | GYRO_FS_250DPS)

    logger.debug("gyroacc_init_sensor_detected and initialized")
    _initialized = True

def get_data():
    """
    public function to read the sensor data.
    the main script calls this repeatedly in a loop.
    """
    if not _initialized:
        init_sensor()

    try:
        return _read_sensor_data()
    except OSError as e:
        logger.error("gyroacc_get_data_error: %s", e)
        return {}