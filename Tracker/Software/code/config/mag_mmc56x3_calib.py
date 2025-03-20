#!/usr/bin/env python3
from smbus2 import SMBus
import time
import math
import json

# use 'agg' backend for matplotlib in headless environments (like raspberry pi zero 2w)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# user-adjustable offsets (initially zero for calibration)
X_OFFSET = 0
Y_OFFSET = 0
Z_OFFSET = 0

# (not used in plotting)
ANGLE_OFFSET = 0.0

MMC56X3_I2C_ADDR = 0x30  # default i2c address for mmc5603/5604/5607, etc.
REG_XOUT_0    = 0x00     # starting register for magnetometer data
REG_CONTROL_0 = 0x1B     # control register (trigger measurement)


# setup smbus
bus = SMBus(1)

def read_magnet_data():
    """
    triggers a single measurement and reads 9 bytes from the sensor.
    data is arranged as follows (per the micropython library for mmc5603):
      - x axis: bytes 0 (msbs) and 1, plus the high nibble of byte 6.
      - y axis: bytes 2 and 3, plus the high nibble of byte 7.
      - z axis: bytes 4 and 5, plus the high nibble of byte 8.
    the 20-bit raw values (two's complement with zero at 2^19) are then scaled.
    returns the magnetometer values in microteslas (ut).
    """
    # trigger a measurement by writing 0x01 to the control register
    bus.write_byte_data(MMC56X3_I2C_ADDR, REG_CONTROL_0, 0x01)
    time.sleep(0.002)  # wait for measurement to complete

    # read 9 bytes starting at register reg_xout_0
    data = bus.read_i2c_block_data(MMC56X3_I2C_ADDR, REG_XOUT_0, 9)

    # parse the raw 20-bit data for each axis
    x_raw = (data[0] << 12) | (data[1] << 4) | (data[6] >> 4)
    y_raw = (data[2] << 12) | (data[3] << 4) | (data[7] >> 4)
    z_raw = (data[4] << 12) | (data[5] << 4) | (data[8] >> 4)
    
    # convert from unsigned 20-bit to signed value (two's complement)
    x_raw -= 1 << 19  # 2^19 = 524288
    y_raw -= 1 << 19
    z_raw -= 1 << 19

    # scale to physical units (microteslas)
    x_uT = x_raw * 0.00625
    y_uT = y_raw * 0.00625
    z_uT = z_raw * 0.00625

    return x_uT, y_uT, z_uT

def collect_data(num_samples=100, delay=0.01):
    """
    collects magnetometer data over a given number of samples.
    returns three lists: xs, ys, and zs.
    """
    xs, ys, zs = [], [], []
    print("mag_calib_collect_data_collecting magnetometer data...")
    for i in range(num_samples):
        try:
            x, y, z = read_magnet_data()
            # for calibration, we do not subtract any offsets yet
            xs.append(x)
            ys.append(y)
            zs.append(z)
            print("mag_calib_collect_data_sample %d: x=%.2f ut, y=%.2f ut, z=%.2f ut", i+1, x, y, z)
            time.sleep(delay)
        except KeyboardInterrupt:
            print("mag_calib_collect_data_keyboardinterrupt: data collection interrupted by user")
            break
        except Exception as e:
            print("mag_calib_collect_data_error: %s", e)
            break
    return xs, ys, zs

def calibrate_offsets(xs, ys, zs):
    """
    calculates the offset for each axis as the average of the min and max values.
    returns a tuple of offsets: (x_offset, y_offset, z_offset).
    """
    x_offset = (min(xs) + max(xs)) / 2
    y_offset = (min(ys) + max(ys)) / 2
    z_offset = (min(zs) + max(zs)) / 2
    return x_offset, y_offset, z_offset

def plot_data(xs, ys, zs, title, filename, marker_size=2):
    """
    plots three scatter series on one graph:
      - x vs. y (red)
      - x vs. z (blue)
      - y vs. z (green)
    saves the plot as a png file.
    
    marker_size: size of the dots (smaller for a denser plot).
    """
    plt.figure(figsize=(8, 6))
    plt.scatter(xs, ys, c='r', label='x vs y', alpha=0.7, s=marker_size)
    plt.scatter(xs, zs, c='b', label='x vs z', alpha=0.7, s=marker_size)
    plt.scatter(ys, zs, c='g', label='y vs z', alpha=0.7, s=marker_size)
    plt.xlabel('value')
    plt.ylabel('value')
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    print("mag_calib_plot_data_plot saved as %s", filename)

def main():
    # collect a large set of data for calibration
    num_samples = 2000
    xs, ys, zs = collect_data(num_samples=num_samples, delay=0.01)
    
    # calculate offsets from the collected data
    x_offset, y_offset, z_offset = calibrate_offsets(xs, ys, zs)
    offsets = {"X_OFFSET": x_offset, "Y_OFFSET": y_offset, "Z_OFFSET": z_offset}
    
    # save the calibration offsets to a json file
    try:
        with open("mag_offsets.json", "w") as f:
            json.dump(offsets, f, indent=4)
        print("mag_calib_main_calibration offsets saved to mag_offsets.json")
    except Exception as e:
        print("mag_calib_main_error saving calibration offsets: %s", e)
    
    # plot the raw (uncorrected) data
    plot_data(xs, ys, zs, "raw magnetometer data", "mag_data_raw.png", marker_size=2)
    
    # apply the calculated offsets to correct the data
    xs_corrected = [x - x_offset for x in xs]
    ys_corrected = [y - y_offset for y in ys]
    zs_corrected = [z - z_offset for z in zs]
    
    # plot the offset-corrected data
    plot_data(xs_corrected, ys_corrected, zs_corrected,
              "offset-corrected magnetometer data",
              "mag_data_corrected.png",
              marker_size=2)

if __name__ == "__main__":
    main()
