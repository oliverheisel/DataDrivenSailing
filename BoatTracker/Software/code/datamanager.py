import time
import threading
import paho.mqtt.client as mqtt
import json
import sqlite3
from config import config
import uuid
import queue
import os

# MQTT Broker Configuration
MQTT_BROKER = config.mqtt_broker
MQTT_PORT = config.mqtt_port
MQTT_LiveData = config.mqtt_boatlive
MQTT_Control = config.mqtt_boatcontrol
MQTT_BoatStatus = config.mqtt_boatstatus

MQTT_CLIENT_ID = f"{config.identifier}_{uuid.uuid4().hex[:8]}"
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)

wifi_conn = False
latest_data = {}
streamdata = True   # Default is True (data will be published)
logdata = True      # Default is True (data will be logged to DB)
deletelog = False
deletelogstatus = "-"

# Queue for passing data to the database thread
data_queue = queue.Queue()

# SQLite Database File
DB_FILE = f'/home/globaladmin/data/datalog_{config.identifier}.db'

# Global variables to hold the database connection and cursor
conn = None
cursor = None

def datatransfer(data, wifi_status):
    """
    Publishes sensor data to the MQTT broker if streamdata is True.
    Also pushes data to the database queue.
    Converts data into valid JSON format before sending.
    """
    global wifi_conn, latest_data, streamdata
    wifi_conn = wifi_status
    latest_data = data

    # Ensure that the data is properly formatted into JSON
    try:
        json_data = json.dumps(data, default=str)  # Converts None to null, True to true, etc.
        data_queue.put(data)
        # Check if streamdata is True before publishing data
        if streamdata:
            try:
                mqtt_client.publish(MQTT_LiveData, json_data)  # Publish the JSON-formatted data
                #print(f"Published Data: {json_data}")
            except Exception as e:
                print(f"Error publishing data: {e}")
        else:
            print("streamdata is False, data not published.")
    except Exception as e:
        print(f"Error converting data to JSON: {e}")


def mqtt_loop():
    """
    Manages the MQTT connection, handles automatic reconnections,
    subscribes to the topic, and processes incoming messages.
    """
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(MQTT_Control)
            print("Connected to MQTT Broker and subscribed to control topic.")
        else:
            print(f"Failed to connect, return code {rc}")

    def on_message(client, userdata, msg):
        global streamdata, logdata, deletelog
        try:
            message = msg.payload.decode(errors='ignore')
            if msg.topic == MQTT_Control:
                config_data = json.loads(message)
                streamdata = config_data.get('streamdata', True)
                logdata = config_data.get('logdata', True)
                deletelog = config_data.get('deletelog', False)
                print(f"Received control message: "
                      f"streamdata={streamdata}, logdata={logdata}, deletelog={deletelog}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_forever()  # Use this instead of loop_start() in a dedicated thread
        except Exception as e:
            print(f"MQTT Connection Failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def publish_boatstatus():
    """
    Publishes the boat status every 2 seconds.
    The status contains:
      - config.identifier
      - streamdata
      - logdata
      - deletelogstatus
    """
    while True:
        try:
            status_payload = json.dumps({
                "identifier": config.identifier,
                "streamdata": streamdata,
                "logdata": logdata,
                "deletelogstatus": deletelogstatus
            })
            mqtt_client.publish(MQTT_BoatStatus, status_payload)
            print(f"Published boat status: {status_payload}")
        except Exception as e:
            print(f"Error publishing boat status: {e}")
        time.sleep(2)

def init_db():
    """Initialize the SQLite database and create the table if it doesn't exist."""
    global conn, cursor  # Declare these as global to modify them outside this function

    db_dir = os.path.dirname(DB_FILE)
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            print(f"Created directory: {db_dir}")
        except Exception as e:
            print(f"Error creating directory: {e}")
            return None

    try:
        # Open the database connection once and keep it open
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)  # Allowing for safe access from multiple threads
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logdata (
                datetime TEXT,
                status TEXT,
                lat REAL,
                long REAL,
                SOG TEXT,
                COG TEXT,
                fixQ TEXT,
                nSat TEXT,
                HDOP TEXT,
                alt TEXT,
                id TEXT,
                validtime BOOLEAN,
                batvolt REAL,
                batperc REAL,
                wifi_conn BOOLEAN,
                wifi_signal_strength TEXT
            )
        ''')
        conn.commit()
        print(f"Database initialized at {DB_FILE}")
    except Exception as e:
        print(f"Error initializing database: {e}")

def log_data_to_db():
    """
    Continuously pulls data from the queue and logs it to the database
    if `validtime == True` and `logdata == True`.
    """
    while True:
        # Get data from the queue (this will block until data is available)
        data = data_queue.get()

        # Check if logging is allowed based on validtime and logdata
        if data.get('validtime', False) and logdata:
            # Replace empty strings with None for database insertion
            for key, value in data.items():
                if value == '':
                    data[key] = None

            try:
                # Use the shared connection and cursor to insert the data
                cursor.execute('''
                    INSERT INTO logdata (datetime, status, lat, long, SOG, COG, fixQ, nSat, HDOP, alt, id, validtime, batvolt, batperc, wifi_conn, wifi_signal_strength)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['datetime'], data['status'], data['lat'], data['long'], data['SOG'], data['COG'],
                    data['fixQ'], data['nSat'], data['HDOP'], data['alt'], data['id'], data['validtime'],
                    data['batvolt'], data['batperc'], data['wifi_conn'], data['wifi_signal_strength']
                ))
                conn.commit()
                #print(f"Data logged to database: {data}")
            except Exception as e:
                print(f"Error inserting data into database: {e}")
        else:
            print(f"Skipping data (validtime={data.get('validtime')}, logdata={logdata})")

        # Mark the task as done
        data_queue.task_done()

def handle_delete_log():
    """
    Continuously monitors the global `deletelog` flag.
    When `deletelog` is True:
      - set `logdata` to False
      - set `deletelogstatus` to "deleting"
      - DELETE all rows in the logdata table
      - set `deletelogstatus` to "deleted"
      - wait until `deletelog` goes back to False
      - set `deletelogstatus` to "-"
      - restore `logdata` (e.g., True or from last config)
    """
    global deletelogstatus, logdata, deletelog

    while True:
        # Wait until deletelog becomes True
        if deletelog:
            # Stop logging while deleting
            logdata = False
            deletelogstatus = "deleting"

            try:
                # Delete all rows from the logdata table
                cursor.execute("DELETE FROM logdata")
                conn.commit()
                deletelogstatus = "deleted"
                print("All log data deleted from the database.")

            except Exception as e:
                deletelogstatus = f"Error: {e}"
                print(f"Error deleting log data: {e}")

            # Stay in this state until deletelog goes back to False
            while deletelog:
                time.sleep(1)

            # Once user sets deletelog back to False, reset status and logdata
            deletelogstatus = "-"
            # You can decide whether to restore logdata to True, or read from the last known MQTT config.
            logdata = True

        time.sleep(1)
