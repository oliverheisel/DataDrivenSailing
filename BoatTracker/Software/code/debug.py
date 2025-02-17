def debug_led():
    # Dictionary mapping color names to RGB values
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
            print(f"LED color: {color_name} - RGB: {color_value}")  # Print color name and RGB
            time.sleep(1)
            led.set_color(*led.off)  # Turn off LED
            time.sleep(1)

def debug_gps():
    """
    Continuously prints GPS data for debugging.
    """
    while True:
        threading.Thread(target=gps.read_gps, daemon=True).start()
        data = gps.get_data()
        print("GPS Data:", data)
        time.sleep(0.1)  # Print every second

def debug_battery():
    while True:
        data = battery.get_battery_json()
        print(data)
        time.sleep(1)  # Print every second

def debug_print_db():
    """Connect to the database and print the first 100 rows."""
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Query to select the first 100 rows from the logdata table
        cursor.execute("SELECT * FROM logdata LIMIT 500")

        # Fetch the first 100 rows
        rows = cursor.fetchall()

        if rows:
            print(f"Printing the first {len(rows)} rows from the database:")
            for row in rows:
                print(row)
        else:
            print("No data found in the database.")

        # Close the connection
        conn.close()

    except sqlite3.Error as e:
        print(f"Error reading the database: {e}")


if __name__ == "__main__":
    choice = input("""What do you want to debug? \n 1. LED \n 2. GPS \n 3. Battery \n 4. Database \n 4. Exit \n""")
    if choice == "1":
        from modules import led
        import time
        debug_led()
    elif choice == "2":
        import time
        from modules import gps
        import threading
        debug_gps()
    elif choice == "3":
        import time
        from modules import battery
        debug_battery()
    elif choice == "4":
        DB_FILE = '/home/globaladmin/data/datalog.db'
        import sqlite3
        debug_print_db()
    else:
        print("Exiting...")
