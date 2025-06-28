import pigpio
from config import config
import time
import datamanager
import logging
import sys

# initialize logger for this module
logger = logging.getLogger(__name__)

# initialize pigpio daemon for hardware pwm control
pi = pigpio.pi()

# ensure pigpio successfully connected
if not pi.connected:
    logger.error("led_main_failed to connect to pigpio daemon. make sure pigpio is running with 'sudo pigpiod'")
    sys.exit()

# set up led pins using pwm (using broadcom pin numbering as defined in config.py)
LED_R = int(config.led_r)  # ensure values are integers
LED_G = int(config.led_g)
LED_B = int(config.led_b)

# set pwm frequency for each led pin
pi.set_PWM_frequency(LED_R, 1000)
pi.set_PWM_frequency(LED_G, 1000)
pi.set_PWM_frequency(LED_B, 1000)

# define color values as rgb tuples (max value 255 for raspberry pi pwm control)
red    = (255, 0, 0)
green  = (0, 255, 0)
blue   = (0, 0, 255)
orange = (175, 12, 0)
pink   = (255, 0, 128)
off    = (0, 0, 0)

# define flash speeds in seconds
fast = 0.1  # 100ms per flash
mid  = 0.3  # 300ms per flash
slow = 1.0  # 1 second per flash

# predefined scenarios (tuple format: (color, flash duration, flash count))
error                   = (red,    fast, 5)
invalidgps              = (orange, fast, 1)  # validtime == false & status == "V" (not connected)
invalidgpsconncected    = (orange, fast, 2)  # validtime == false & status == "V" (connected)
validtime               = (blue,   fast, 1)  # validtime == true  & status == "V" (not connected)
validtimeconnected      = (blue,   fast, 2)  # validtime == true  & status == "V" (connected)
validtimeconnectednolog = (blue,   fast, 3)  # validtime == true  & status == "V" (connected) & logdata == false
valid                   = (pink,   fast, 1)  # validtime == true  & status == "A" (not connected)
validnolog              = (pink,   fast, 1)  # validtime == true  & status == "A" (not connected) & logdata == false
validconnected          = (pink,   fast, 2)  # validtime == true  & status == "A" (connected)
validconnectednolog     = (pink,   fast, 3)  # validtime == true  & status == "A" (connected) & logdata == false

# global flag to trigger an error scenario externally
error_triggered = False

def trigger_error():
    """
    external function to trigger the error led scenario.
    when called, the next iteration of led_loop() will flash the error pattern and then resume normal operation.
    """
    global error_triggered
    error_triggered = True

def set_color(r, g, b):
    """sets the led to a specific rgb color."""
    pi.set_PWM_dutycycle(LED_R, r)
    pi.set_PWM_dutycycle(LED_G, g)
    pi.set_PWM_dutycycle(LED_B, b)

def led_flash(color, flashtype, flash_count):
    """flashes the led in a given color for a specified number of times."""
    for _ in range(flash_count):
        set_color(*color)
        time.sleep(flashtype)
        set_color(*off)
        time.sleep(flashtype)

def led_scenario(scenario):
    """executes a predefined led scenario."""
    if isinstance(scenario, tuple) and len(scenario) == 3:
        color, flashtype, flash_count = scenario
        led_flash(color, flashtype, flash_count)
    else:
        logger.error("led_led_scenario_invalid scenario format. no led action taken.")

def led_loop():
    """
    continuously updates the led indicator based on the current sensor data.
    scenarios are chosen based on:
      - validtime == false & status == "V"  → invalidgps (or invalidgpsconncected if connected)
      - validtime == true  & status == "V"  → validtime (or validtimeconnected if connected)
      - validtime == true  & status == "A"  → valid (or validconnected if connected)
    connectivity is defined as both wifi and mqtt being connected.
    
    if trigger_error() is called, the error scenario will be executed once before returning to normal behavior.
    """
    global error_triggered
    while True:
        # if an external error trigger has been set, execute the error scenario
        if error_triggered:
            led_scenario(error)
            error_triggered = False
        else:
            # access global variables from datamanager
            wifi_connected = datamanager.wifi_conn  # check if wifi is connected
            mqtt_connected = (datamanager.mqtt_client is not None and 
                              datamanager.mqtt_client.is_connected())  # check if mqtt is connected
            connectivity = wifi_connected and mqtt_connected  # both must be true for full connectivity

            latest_data = datamanager.latest_data  # get latest sensor data
            current_led_scenario = None  # local variable to store the led scenario

            if latest_data:
                data_validtime = latest_data.get("validtime", False)
                status = latest_data.get("status", None)
                logdata = datamanager.logdata

                current_led_scenario = None

                if status == "V":
                    if data_validtime:
                        # validtime == true & status == "V"
                        if logdata:
                            current_led_scenario = validtimeconnected if connectivity else validtime
                        else:
                            current_led_scenario = validtimeconnectednolog if connectivity else validtime
                    else:
                        # validtime == false & status == "V"
                        current_led_scenario = invalidgpsconncected if connectivity else invalidgps

                elif status == "A":
                    if data_validtime:
                        # validtime == true & status == "A"
                        if logdata:
                            current_led_scenario = validconnected if connectivity else valid
                        else:
                            current_led_scenario = validconnectednolog if connectivity else validnolog
                    else:
                        # validtime == false & status == "A"
                        current_led_scenario = invalidgpsconncected if connectivity else invalidgps
                else:
                    current_led_scenario = None

            # update the led based on the selected scenario
            if current_led_scenario is not None:
                led_scenario(current_led_scenario)

        time.sleep(0.5)  # adjust loop delay to balance responsiveness and cpu usage
