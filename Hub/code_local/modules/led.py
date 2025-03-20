import RPi.GPIO as GPIO
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
    print("Failed to connect to pigpio daemon. Make sure pigpio is running with 'sudo pigpiod'")
    exit()

# set up led pins using pwm (use broadcom pin numbering as defined in config.py)
LED_R = int(config.led_r)  # ensure values are integers
LED_G = int(config.led_g)
LED_B = int(config.led_b)

# set pwm frequency
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

# predefined scenarios:
error                = (red,    fast, 5)
invalidgps           = (orange, fast, 1)  # validtime == False & status == "V" (not connected)
invalidgps_connected = (orange, fast, 2)  # validtime == False & status == "V" (connected)
validtime            = (blue,   fast, 1)  # validtime == True  & status == "V" (not connected)
validtimeconnected   = (blue,   fast, 2)  # validtime == True  & status == "V" (connected)
valid                = (pink,   fast, 1)  # validtime == True  & status == "A" (not connected)
validconnected       = (pink,   fast, 2)  # validtime == True  & status == "A" (connected)

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
        logger.error("led_scenario: Invalid scenario format. No LED action taken.")

def led_loop():
    """
    continuously updates the led indicator based on the current sensor data.
    scenarios are chosen based on:
      - for status "V":
          • if validtime is True: use validtimeconnected when connected, else validtime.
          • if validtime is False: use invalidgps_connected when connected, else invalidgps.
      - for status "A":
          • if validtime is True: use validconnected when connected, else valid.
          • if validtime is False: no led action is taken.
    connectivity is determined by the mqtt connection status.
    """
    global error_triggered
    while True:
        # if an external error trigger has been set, execute the error scenario
        if error_triggered:
            led_scenario(error)
            error_triggered = False
        else:
            # access global variables from datamanager
            mqtt_connected = (
                datamanager.mqtt_client is not None and 
                datamanager.mqtt_client.is_connected()
            )
            connectivity = mqtt_connected  # both must be true for full connectivity

            latest_data = datamanager.latest_data  # get latest sensor data
            current_led_scenario = None  # local variable to store the led scenario

            if latest_data:
                data_validtime = latest_data.get("validtime", False)  # check if the data is valid
                status = latest_data.get("status", None)  # get the sensor status ("V" or "A")

                if status == "V":
                    if data_validtime:
                        # validtime == True & status == "V"
                        current_led_scenario = validtimeconnected if connectivity else validtime
                    else:
                        # validtime == False & status == "V"
                        current_led_scenario = invalidgps_connected if connectivity else invalidgps

                elif status == "A":
                    if data_validtime:
                        # validtime == True & status == "A"
                        current_led_scenario = validconnected if connectivity else valid
                    else:
                        # no led action for invalid gps data when status is "A"
                        current_led_scenario = None
                else:
                    # for any unrecognized status, no led action is taken.
                    current_led_scenario = None

            # update the led based on the selected scenario
            if current_led_scenario is not None:
                led_scenario(current_led_scenario)

        time.sleep(0.5)  # adjust loop delay to balance responsiveness and cpu usage
