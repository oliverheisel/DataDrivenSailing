import sys
import time
import threading
import logging
from config import config
from modules import led, gps, wind, mag
import datamanager
import errordebuglogger

# set up logger
logger = logging.getLogger(__name__)

# global variables to hold sensor data
gps_data = None   # latest GPS data
wind_data = None  # latest wind sensor data
mag_data = None

def mainloop():
    """
    processes sensor data, calculates true wind direction, and publishes merged data.
    """
    global gps_data, wind_data, mag_data
    last_time = None

    while True:
        # if no GPS data is available yet, wait a bit and continue
        if gps_data is None:
            time.sleep(0.8)
            continue

        # if GPS data is a dictionary and has a datetime, wait until it updates
        if isinstance(gps_data, dict) and gps_data.get("datetime") is not None:
            current_time = gps_data.get("datetime")
            # wait until a new GPS timestamp is available
            while current_time == last_time:
                time.sleep(0.001)
                current_time = gps_data.get("datetime")
            last_time = current_time
            sleep_interval = 0.001
        else:
            sleep_interval = 0.1

        # merge data from different sensors into one dictionary
        merged_data = {}
        merged_data.update(gps_data)
        merged_data["id"] = config.identifier
        merged_data["validtime"] = gps_data.get("datetime") is not None

        # add wind sensor data if available
        if wind_data is not None:
            merged_data.update(wind_data)

        # add magnetometer data if available
        if mag_data is not None:
            merged_data.update(mag_data)

        # calculate the true wind direction if both heading and wind angle are available
        try:
            # heading: the direction the device is pointing
            # w_angle: wind angle relative to the device's heading
            heading = float(merged_data.get("heading", 0))
            w_angle = float(merged_data.get("w_angle", 0))
            true_wind_direction = (heading + w_angle) % 360
            merged_data["true_wind_dir"] = round(true_wind_direction, 2)
        except (ValueError, TypeError):
            # if conversion fails, we don't add true wind direction
            merged_data["true_wind_dir"] = None

        # log merged sensor data
        logger.debug("mainloop_merged data: %s", merged_data)
        datamanager.datatransfer(merged_data)
        time.sleep(sleep_interval)


def sensor1_gps():
    """
    continuously updates the global gps_data variable.
    """
    global gps_data
    while True:
        gps_data = gps.get_data()
        time.sleep(0.01)

def sensor2_wind():
    """
    periodically fetches the latest wind sensor data from the wind module.
    """
    global wind_data
    while True:
        wind_data = wind.get_wind_data()
        time.sleep(0.1)

def sensor3_mag():
    """
    continuously updates the global mag_data variable.
    """
    global mag_data
    while True:
        # get new magnetometer data from the mag module
        mag_data = mag.get_data()
        time.sleep(0.01)

def main():
    try:
        gps.init_gps()
    except Exception as e:
        logger.error("main_init_gps_error: %s", str(e))
    else:
        logger.debug("main_init_gps_success")

    # start MQTT, LED, and GPS reading threads
    threading.Thread(target=datamanager.mqtt_loop, daemon=True).start()
    threading.Thread(target=led.led_loop, daemon=True).start()
    threading.Thread(target=gps.read_gps, daemon=True).start()
    threading.Thread(target=sensor1_gps, daemon=True).start()

    # start the wind sensor read loop in its own thread
    threading.Thread(target=wind.wind_sensor_loop, daemon=True).start()
    threading.Thread(target=sensor2_wind, daemon=True).start()

    # start sensor thread for magnetometer data
    threading.Thread(target=sensor3_mag, daemon=True).start()

    # start the main data merging and publishing loop
    threading.Thread(target=mainloop, daemon=True).start()

    # keep the main thread alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
