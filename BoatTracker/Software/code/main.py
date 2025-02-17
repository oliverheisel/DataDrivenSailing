import sys
import time
import threading
from config import config
from modules import led, gps, battery  # Now this should work without circular import issues
import datamanager

# Global variables for sensor data
wifi_conn = None  # WiFi connection state
wifi_signal_strength = None  # WiFi signal strength
gps_data = None   # Latest GPS data
bat_data = None   # Battery data as a dictionary

def mainloop():
    """
    Processes sensor data and publishes merged data.
    """
    global gps_data, bat_data, wifi_conn
    last_time = None

    while True:
        if gps_data is None:
            time.sleep(0.8)
            continue

        if isinstance(gps_data, dict) and gps_data.get("datetime") is not None:
            current_time = gps_data.get("datetime")
            while current_time == last_time:
                time.sleep(0.02)
                current_time = gps_data.get("datetime")
            last_time = current_time
            sleep_interval = 0.1
        else:
            sleep_interval = 0.8

        merged_data = {}
        merged_data.update(gps_data)
        merged_data["id"] = config.identifier
        merged_data["validtime"] = gps_data.get("datetime") is not None

        if bat_data is not None:
            merged_data.update(bat_data)

        # Append WiFi connection status and signal strength to the dictionary.
        merged_data["wifi_conn"] = wifi_conn
        merged_data["wifi_signal_strength"] = wifi_signal_strength

        #print(merged_data)
        datamanager.datatransfer(merged_data, wifi_conn)
        time.sleep(sleep_interval)

def sensor1_gps():
    """
    Continuously updates the global gps_data variable.
    """
    global gps_data
    while True:
        gps_data = gps.get_data()
        time.sleep(0.01)

def sensor4_battery():
    """
    Continuously updates the global bat_data variable with battery data.
    """
    global bat_data
    while True:
        try:
            bat_data = battery.get_battery_json()
        except Exception as e:
            # Optionally log or handle the exception
            bat_data = {}  # Use an empty dict if battery data is unavailable
        time.sleep(2)

def wifi_monitor():
    """
    Continuously monitors the WiFi connection status and signal strength.
    
    This function reads the connection state from:
      /sys/class/net/wlan0/operstate
      
    And the signal strength (in dBm) from:
      /proc/net/wireless
      
    It then prints the status. Adjust the sleep interval as needed.
    """
    global wifi_conn, wifi_signal_strength

    while True:
        # Check if wlan0 is up by reading the operstate file.
        try:
            with open('/sys/class/net/wlan0/operstate', 'r') as f:
                state = f.read().strip()
            wifi_conn = (state == 'up')
        except Exception:
            wifi_conn = False

        # If connected, read the signal strength from /proc/net/wireless.
        if wifi_conn:
            try:
                with open('/proc/net/wireless', 'r') as f:
                    lines = f.readlines()
                # The first two lines are headers, so check subsequent lines.
                for line in lines[2:]:
                    if 'wlan0:' in line:
                        parts = line.split()
                        # Typical format: 
                        # wlan0: 0000   54.  -56.  -256  ... 
                        # Here, parts[3] is usually the signal level in dBm.
                        wifi_signal_strength = parts[3]
                        break
            except Exception:
                wifi_signal_strength = None
        else:
            wifi_signal_strength = None

        # Print the current WiFi connection status and signal strength.
        #print(f"WiFi connected: {wifi_conn}, Signal strength: {wifi_signal_strength}")
        
        # Sleep for a second (adjust as needed; process is not time-critical)
        time.sleep(0.2)


def main():
    """
    Initializes and starts all required threads.
    """
    conn = datamanager.init_db()
    if conn:
        print("Database initialized successfully.")
    else:
        print("Database initialization failed.")

    threading.Thread(target=wifi_monitor, daemon=True).start()

    threading.Thread(target=datamanager.mqtt_loop, daemon=True).start()   # Start the MQTT connection thread
    threading.Thread(target=datamanager.publish_boatstatus, daemon=True).start() 
    threading.Thread(target=datamanager.log_data_to_db, daemon=True).start()
    threading.Thread(target=datamanager.handle_delete_log, daemon=True).start()  
    threading.Thread(target=led.led_loop, daemon=True).start()

    # Start the GPS reading thread from the GPS module
    threading.Thread(target=gps.read_gps, daemon=True).start()
    # Start the sensor thread that updates the global gps_data variable
    threading.Thread(target=sensor1_gps, daemon=True).start()
    # Start the battery sensor thread
    threading.Thread(target=sensor4_battery, daemon=True).start()
    # Start the main loop that processes and sends merged sensor data
    threading.Thread(target=mainloop, daemon=True).start()

    # Keep the main thread alive
    while True: 
        time.sleep(1)

if __name__ == "__main__":
    main()
