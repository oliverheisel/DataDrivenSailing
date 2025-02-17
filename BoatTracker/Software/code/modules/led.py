import RPi.GPIO as GPIO
import pigpio
from config import config
import time
import datamanager

# Initialize pigpio daemon for hardware PWM control
pi = pigpio.pi()

# Ensure pigpio successfully connected
if not pi.connected:
    print("Failed to connect to pigpio daemon. Make sure pigpio is running with 'sudo pigpiod'")
    exit()

# Set up LED pins using PWM (use Broadcom pin numbering as defined in config.py)
LED_R = int(config.led_r)  # Ensure values are integers
LED_G = int(config.led_g)
LED_B = int(config.led_b)

# Set PWM frequency
pi.set_PWM_frequency(LED_R, 1000)
pi.set_PWM_frequency(LED_G, 1000)
pi.set_PWM_frequency(LED_B, 1000)

# Define color values as RGB tuples (max value 255 for Raspberry Pi PWM control)
red    = (255, 0, 0)
green  = (0, 255, 0)
blue   = (0, 0, 255)
orange = (175, 12, 0)
pink   = (255, 0, 128)
off    = (0, 0, 0)

# Define flash speeds in seconds
fast = 0.1  # 100ms per flash
mid  = 0.3  # 300ms per flash
slow = 1.0  # 1 second per flash

# Predefined scenarios:
error                  = (red,    fast, 5)
invalidgps             = (orange, fast, 1)  # validtime == False & status == "V" (not connected)
invalidgpsconncected   = (orange, fast, 2)  # validtime == False & status == "V" (connected)
validtime              = (blue,   fast, 1)  # validtime == True  & status == "V" (not connected)
validtime              = (blue,   fast, 1)  # validtime == True  & status == "V" (not connected) & logdata == False
validtimeconnected     = (blue,   fast, 2)  # validtime == True  & status == "V" (connected)
validtimeconnectednolog     = (blue,   fast, 3)  # validtime == True  & status == "V" (connected) & logdata == False
valid                  = (pink,   fast, 1)  # validtime == True  & status == "A" (not connected)
validnolog                  = (pink,   fast, 1)  # validtime == True  & status == "A" (not connected) & logdata == False
validconnected         = (pink,   fast, 2)  # validtime == True  & status == "A" (connected)
validconnectednolog         = (pink,   fast, 3)  # validtime == True  & status == "A" (connected) & logdata == False

def set_color(r, g, b):
    """Sets the LED to a specific RGB color."""
    pi.set_PWM_dutycycle(LED_R, r)
    pi.set_PWM_dutycycle(LED_G, g)
    pi.set_PWM_dutycycle(LED_B, b)

def led_flash(color, flashtype, flash_count):
    """Flashes the LED in a given color for a specified number of times."""
    for _ in range(flash_count):
        set_color(*color)
        time.sleep(flashtype)
        set_color(*off)
        time.sleep(flashtype)

def led_scenario(scenario):
    """Executes a predefined LED scenario."""
    if isinstance(scenario, tuple) and len(scenario) == 3:
        color, flashtype, flash_count = scenario
        led_flash(color, flashtype, flash_count)
    else:
        print("Invalid scenario format. No LED action taken.")

def led_loop():
    """
    Continuously updates the LED indicator based on the current sensor data.
    Scenarios are chosen based on:
      - validtime == False & status == "V"  → invalidgps (or invalidgpsconncected if connected)
      - validtime == True  & status == "V"  → validtime (or validtimeconnected if connected)
      - validtime == True  & status == "A"  → valid (or validconnected if connected)
    Connectivity is defined as both WiFi and MQTT being connected.
    """
    while True:
        # Access global variables from datamanager
        wifi_connected = datamanager.wifi_conn  # Check if WiFi is connected
        mqtt_connected = (datamanager.mqtt_client is not None and datamanager.mqtt_client.is_connected())  # Check if MQTT is connected
        connectivity = wifi_connected and mqtt_connected  # Both must be True for full connectivity

        latest_data = datamanager.latest_data  # Get latest sensor data
        current_led_scenario = None  # Local variable to store the LED scenario

        if latest_data:
            data_validtime = latest_data.get("validtime", False)  # Check if the data is valid
            status = latest_data.get("status", None)  # Get the sensor status ("V" or "A")
            logdata = datamanager.logdata  # Access the global logdata flag

            # Check different scenarios based on status, validtime, connectivity, and logdata
            if status == "V":
                if data_validtime:
                    # validtime == True & status == "V"
                    if logdata:
                        current_led_scenario = validtimeconnected if connectivity else validtime
                    else:
                        current_led_scenario = validtimeconnectednolog if connectivity else validtime
                else:
                    # validtime == False & status == "V"
                    current_led_scenario = invalidgpsconncected if connectivity else invalidgps

            elif status == "A":
                if data_validtime:
                    # validtime == True & status == "A"
                    if logdata:
                        current_led_scenario = validconnected if connectivity else valid
                    else:
                        current_led_scenario = validconnectednolog if connectivity else validnolog
                else:
                    # Invalid GPS data for status "A", should not typically occur, but handle if needed
                    current_led_scenario = None  # No specific LED action for invalid GPS data with "A"

            else:
                # If status is not recognized (not "A" or "V"), use error scenario
                pass
                #current_led_scenario = error

        # Update the LED based on the selected scenario
        if current_led_scenario is not None:
            led_scenario(current_led_scenario)

        # Optional debugging (useful for troubleshooting or confirming which scenario is chosen):
        # print(f"LED Scenario: {current_led_scenario}, WiFi: {wifi_connected}, MQTT: {mqtt_connected}, Data: {latest_data}")

        time.sleep(0.5)  # Adjust loop delay to balance responsiveness and CPU usage
