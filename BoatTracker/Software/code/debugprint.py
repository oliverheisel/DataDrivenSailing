import time
import threading

def debug_gps():
    """
    Continuously prints GPS data for debugging.
    """
    from modules import gps
    while True:
        threading.Thread(target=gps.read_gps, daemon=True).start()
        data = gps.get_data()
        print("GPS Data:", data)
        time.sleep(0.1)  # Print every 0.1 seconds

def debug_gyroacc():
    """
    Continuously prints Gyroscope/Accelerometer data for debugging.
    """
    from modules import gyroacc
    while True:
        data = gyroacc.get_data()
        print("Gyro/ACC Data:", data)
        time.sleep(0.1)

def debug_mag():
    """
    Continuously prints magnetometer data for debugging.
    """
    from modules import mag
    while True:
        data = mag.get_data()  # Data contains mag_x, mag_y, mag_z, and heading (all rounded)
        print("Mag Data:", data)
        time.sleep(0.1)

def debug_battery():
    """
    Continuously prints battery data for debugging.
    """
    from modules import battery
    while True:
        data = battery.get_battery_json()
        print("Battery Data:", data)
        time.sleep(1)

def debug_led():
    """
    Continuously cycles through predefined LED colors for debugging.
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
            led.set_color(*color_value)  # Unpack RGB values
            print(f"LED color: {color_name} - RGB: {color_value}")
            time.sleep(1)
            led.set_color(*led.off)  # Turn off LED
            time.sleep(1)

def debug_print_db():
    """
    Connect to the database and print the first 500 rows,
    then print the column header at the bottom.
    """
    from config import config
    import sqlite3

    DB_FILE = f'/home/globaladmin/data/datalog_{config.identifier}.db'
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM logdata LIMIT 500")
        rows = cursor.fetchall()
        if rows:
            print(f"Printing the first {len(rows)} rows from the database:")
            for row in rows:
                print(row)
            # Get and print the column headers from the cursor description.
            header = [description[0] for description in cursor.description]
            print("\nHeader (Column Names):")
            print(header)
        else:
            print("No data found in the database.")
        conn.close()
    except sqlite3.Error as e:
        print(f"Error reading the database: {e}")


if __name__ == "__main__":
    choice = input(
        """What do you want to debug? 
1. GPS 
2. Gyro/Accelerometer  
3. Magnetometer
4. Battery 
5. LED
6. Database print
7. Exit 
> """
    )

    if choice == "1":
        debug_gps()
    elif choice == "2":
        debug_gyroacc()
    elif choice == "3":
        debug_mag()
    elif choice == "4":
        debug_battery()
    elif choice == "5":
        debug_led()
    elif choice == "6":
        debug_print_db()
    else:
        print("Exiting...")
