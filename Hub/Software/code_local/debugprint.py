import time
import threading

def debug_gps():
    """
    continuously prints gps data for debugging.
    """
    from modules import gps
    while True:
        threading.Thread(target=gps.read_gps, daemon=True).start()
        data = gps.get_data()
        print("GPS Data:", data)
        time.sleep(0.1)  # print every 0.1 seconds

def debug_mag():
    """
    continuously prints magnetometer data for debugging.
    """
    from modules import mag
    while True:
        data = mag.get_data()  # data contains mag_x, mag_y, mag_z, and heading (all rounded)
        print("Mag Data:", data)
        time.sleep(0.1)

def debug_led():
    """
    continuously cycles through predefined led colors for debugging.
    """
    from modules import led
    colors = {
        "Red": led.red,
        "Green": led.green,
        "Blue": led.blue,
        "Orange": led.orange,
        "Pink": led.pink
    }

    while True:
        for color_name, color_value in colors.items():
            led.set_color(*color_value)  # unpack rgb values
            print(f"LED color: {color_name} - RGB: {color_value}")
            time.sleep(1)
            led.set_color(*led.off)  # turn off led
            time.sleep(1)

def debug_wind():
    """
    continuously prints wind sensor data for debugging.
    """
    from modules import wind
    threading.Thread(target=wind.wind_sensor_loop, daemon=True).start()
    while True:
        print("Wind Data:", wind.get_wind_data())
        time.sleep(0.1)

if __name__ == "__main__":
    choice = input(
        """What do you want to debug? 
1. GPS 
2. Magnetometer
3. LED
4. Wind
5. Exit 
> """
    )

    if choice == "1":
        debug_gps()
    elif choice == "2":
        debug_mag()
    elif choice == "3":
        debug_led()
    elif choice == "4":
        debug_wind()
    else:
        print("Exiting...")
