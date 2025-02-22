import sys
import time
import threading
from config import config
from modules import led, gps, battery, gyroacc, mag
import datamanager
import logging
import errordebuglogger

logger = logging.getLogger(__name__)

ubx_rate_config = [
    0xB5, 0x62,  # ubx header sync chars
    0x06, 0x8A,  # class = cfg (0x06), id = 0x8a (cfg-valset in u-blox m10)
    0x0A, 0x00,  # payload length = 10 bytes
    0x01, 0x01, 0x00, 0x00,  # part of the cfg-valset payload
    0x01, 0x00, 0x21, 0x30,  # additional payload bytes
    0x64, 0x00,              # additional payload bytes
    0x52, 0xC3               # checksum (ck_a, ck_b)
]

# global variables for sensor data
wifi_conn = None             # wifi connection state
wifi_signal_strength = None  # wifi signal strength
gps_data = None              # latest gps data
gyroacc_data = None          # gyroscope and accelerometer data as a dictionary
mag_data = None              # magnetometer data as a dictionary
bat_data = None              # battery data as a dictionary


def mainloop():
    """
    processes sensor data and publishes merged data.
    """
    global gps_data, bat_data, wifi_conn
    last_time = None

    while True:
        # if no gps data is available yet, wait a bit and continue
        if gps_data is None:
            time.sleep(0.8)
            continue

        # if gps data is a dictionary and has a datetime, wait until it updates
        if isinstance(gps_data, dict) and gps_data.get("datetime") is not None:
            current_time = gps_data.get("datetime")
            # wait until new gps timestamp is available
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

        if gyroacc_data is not None:
            merged_data.update(gyroacc_data)

        if mag_data is not None:
            merged_data.update(mag_data)

        if bat_data is not None:
            merged_data.update(bat_data)

        # append wifi connection status and signal strength to the dictionary
        merged_data["wifi_conn"] = wifi_conn
        merged_data["wifi_signal_strength"] = wifi_signal_strength

        # log merged sensor data at debug level
        logger.debug("main_mainloop_merged data: %s", merged_data)
        datamanager.datatransfer(merged_data, wifi_conn)
        time.sleep(sleep_interval)


def sensor1_gps():
    """
    continuously updates the global gps_data variable.
    """
    # start gps reading thread from the gps module
    threading.Thread(target=gps.read_gps, daemon=True).start()

    global gps_data
    while True:
        # get new gps data from the gps module
        gps_data = gps.get_data()
        time.sleep(0.01)


def sensor2_gyroacc():
    """
    continuously updates the global gyroacc_data variable.
    """
    global gyroacc_data
    while True:
        # get new gyroscope and accelerometer data from the gyroacc module
        gyroacc_data = gyroacc.get_data()
        time.sleep(0.01)


def sensor3_mag():
    """
    continuously updates the global mag_data variable.
    """
    global mag_data
    while True:
        # get new magnetometer data from the mag module
        mag_data = mag.get_data()
        time.sleep(0.01)


def sensor4_battery():
    """
    continuously updates the global bat_data variable with battery data.
    """
    global bat_data
    while True:
        try:
            # get battery data in json format from the battery module
            bat_data = battery.get_battery_json()
        except Exception as e:
            # log battery sensor exception and use an empty dict as fallback
            logger.error("main_sensor4_battery_%s", e)
            bat_data = {}  # use an empty dict if battery data is unavailable
        time.sleep(2)


def wifi_monitor():
    """
    continuously monitors the wifi connection status and signal strength.
    
    this function reads the connection state from:
      /sys/class/net/wlan0/operstate
      
    and the signal strength (in dbm) from:
      /proc/net/wireless
      
    it then logs the status. adjust the sleep interval as needed.
    """
    global wifi_conn, wifi_signal_strength

    while True:
        # check if wlan0 is up by reading the operstate file
        try:
            with open('/sys/class/net/wlan0/operstate', 'r') as f:
                state = f.read().strip()
            wifi_conn = (state == 'up')
        except Exception as e:
            logger.error("main_wifi_monitor_error reading operstate: %s", e)
            wifi_conn = False

        # if connected, read the signal strength from /proc/net/wireless
        if wifi_conn:
            try:
                with open('/proc/net/wireless', 'r') as f:
                    lines = f.readlines()
                # the first two lines are headers, so check subsequent lines
                for line in lines[2:]:
                    if 'wlan0:' in line:
                        parts = line.split()
                        # typical format: 
                        # wlan0: 0000   54.  -56.  -256  ... 
                        # here, parts[3] is usually the signal level in dbm
                        wifi_signal_strength = parts[3]
                        break
            except Exception as e:
                logger.error("main_wifi_monitor_error reading wireless info: %s", e)
                wifi_signal_strength = None
        else:
            wifi_signal_strength = None

        # log the current wifi connection status and signal strength at debug level
        logger.debug("main_wifi_monitor_wifi connected: %s, signal strength: %s", wifi_conn, wifi_signal_strength)
        
        # sleep for a short interval (not time-critical)
        time.sleep(0.2)


def main():
    """
    initializes and starts all required threads.
    """
    try:
        gps.init_gps()
    except Exception as e:
        logging.error("main_main_error - gps init error %s", e)
    else:
        logging.debug("main_main_success - gps init success")

    # start wifi monitoring thread
    threading.Thread(target=wifi_monitor, daemon=True).start()

    # start mqtt connection thread
    threading.Thread(target=datamanager.mqtt_loop, daemon=True).start()  # start the mqtt connection thread
    # start boat status publishing thread
    threading.Thread(target=datamanager.publish_boatstatus, daemon=True).start()
    # start data logging to database thread
    threading.Thread(target=datamanager.log_data_to_db, daemon=True).start()
    # start log deletion handling thread
    threading.Thread(target=datamanager.handle_delete_log, daemon=True).start()
    
    # start led control loop thread
    threading.Thread(target=led.led_loop, daemon=True).start()

    # start sensor thread that updates the global gps_data variable
    threading.Thread(target=sensor1_gps, daemon=True).start()
    # start sensor thread for gyroscope and accelerometer data
    threading.Thread(target=sensor2_gyroacc, daemon=True).start()
    # start sensor thread for magnetometer data
    threading.Thread(target=sensor3_mag, daemon=True).start()
    # start sensor thread for battery data
    threading.Thread(target=sensor4_battery, daemon=True).start()
    # start main loop thread that processes and sends merged sensor data
    threading.Thread(target=mainloop, daemon=True).start()

    # keep the main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
