import time
import threading
import paho.mqtt.client as mqtt
import json
import sqlite3
from config import config
import uuid
import queue
import os
import logging

# initialize logger for this module
logger = logging.getLogger(__name__)

# mqtt broker configuration
MQTT_BROKER = config.mqtt_broker
MQTT_PORT = config.mqtt_port
MQTT_LiveData = config.mqtt_boatlive
MQTT_Control = config.mqtt_boatcontrol
MQTT_BoatStatus = config.mqtt_boatstatus

# unique mqtt client id
MQTT_CLIENT_ID = f"{config.identifier}_{uuid.uuid4().hex[:8]}"
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)

# global variables for connection and data states
wifi_conn = False
latest_data = {}
streamdata = True   # default is true (data will be published)
logdata = True      # default is true (data will be logged to db)
deletelog = False
deletelogstatus = "-"

# queue for passing data to the database thread
data_queue = queue.Queue()

# sqlite database file path
DB_FILE = f'/home/globaladmin/data/datalog_{config.identifier}.db'

# global variables to hold the database connection and cursor
conn = None
cursor = None

import time
import json

# global variable to track when we last published
last_publish_time = 0

def datatransfer(data, wifi_status):
    """
    Publishes sensor data to the MQTT broker if streamdata is True.
    Data is published at most once per second using the latest sensor values.
    Also pushes data to the database queue after converting it to valid JSON.
    """
    global wifi_conn, latest_data, streamdata, last_publish_time
    wifi_conn = wifi_status
    latest_data = data

    try:
        # Convert sensor data into JSON format; handles non-serializable types via default=str.
        json_data = json.dumps(data, default=str)

        # Always queue data for DB logging even if not publishing.
        data_queue.put(data)

        if streamdata:
            current_time = time.time()
            # Publish only if at least one second has passed since the last publish.
            if current_time - last_publish_time >= 1:
                last_publish_time = current_time
                try:
                    # Publish the JSON-formatted sensor data to the live data topic.
                    mqtt_client.publish(MQTT_LiveData, json_data)
                    logger.debug("datamanager_datatransfer_published data: %s", json_data)
                except Exception as e:
                    logger.error("datamanager_datatransfer_error publishing data: %s", e)
            else:
                logger.debug("datamanager_datatransfer_skipping publish; waiting for 1-second interval")
        else:
            logger.debug("datamanager_datatransfer_skipping mqtt publish (streamdata=%s)", streamdata)
    except Exception as e:
        logger.error("datamanager_datatransfer_error converting data to json: %s", e)


## this is datatransfer for ever .00Z data
# def datatransfer(data, wifi_status):
#     """
#     publishes sensor data to the mqtt broker if streamdata is true and
#     the datetime's millisecond part equals "00" (i.e., ends with '.00Z').
#     also pushes data to the database queue after converting it to valid json.
#     """
#     global wifi_conn, latest_data, streamdata
#     wifi_conn = wifi_status
#     latest_data = data

#     try:
#         # convert sensor data into json format; handles non-serializable types via default=str
#         json_data = json.dumps(data, default=str)

#         # always queue data for db logging even if not publishing
#         data_queue.put(data)

#         # ensure dt_str is a string even if data.get('datetime') is None
#         dt_str = data.get('datetime') or ''

#         # check if streaming is enabled and if datetime ends with ".00Z"
#         if streamdata and dt_str.endswith('.00Z'):
#             try:
#                 # publish the json-formatted sensor data to the live data topic
#                 mqtt_client.publish(MQTT_LiveData, json_data)
#                 logger.debug("datamanager_datatransfer_published data: %s", json_data)
#             except Exception as e:
#                 logger.error("datamanager_datatransfer_error publishing data: %s", e)
#         else:
#             # skipping mqtt publish because streamdata is false or datetime ms is not .00
#             logger.debug("datamanager_datatransfer_skipping mqtt publish (streamdata=%s, datetime=%s)", streamdata, dt_str)
#     except Exception as e:
#         logger.error("datamanager_datatransfer_error converting data to json: %s", e)


def mqtt_loop():
    """
    manages the mqtt connection, handles automatic reconnections,
    subscribes to the control topic, and processes incoming messages.
    """
    def on_connect(client, userdata, flags, rc):
        # check if connection was successful
        if rc == 0:
            client.subscribe(MQTT_Control)
            logger.debug("datamanager_on_connect_connected to mqtt broker and subscribed to control topic")
        else:
            logger.debug("datamanager_on_connect_failed to connect, return code: %s", rc)

    def on_message(client, userdata, msg):
        global streamdata, logdata, deletelog
        try:
            # decode the incoming message payload
            message = msg.payload.decode(errors='ignore')
            if msg.topic == MQTT_Control:
                # load the control message and update configuration flags
                config_data = json.loads(message)
                streamdata = config_data.get('streamdata', True)
                logdata = config_data.get('logdata', True)
                deletelog = config_data.get('deletelog', False)
                logger.debug("datamanager_on_message_received control message: streamdata=%s, logdata=%s, deletelog=%s", streamdata, logdata, deletelog)
        except json.JSONDecodeError as e:
            logger.error("datamanager_on_message_error decoding json message: %s", e)
        except Exception as e:
            logger.error("datamanager_on_message_error processing message: %s", e)

    # assign the on_connect and on_message callbacks to the mqtt client
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    while True:
        try:
            # attempt to connect to the mqtt broker and enter the network loop
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_forever()
        except Exception as e:
            logger.debug("datamanager_mqtt_loop_mqtt connection failed: %s. retrying in 5 seconds...", e)
            time.sleep(5)


def publish_boatstatus():
    """
    publishes the boat status every 2 seconds.
    the status includes:
      - config.identifier
      - streamdata
      - logdata
      - deletelogstatus
    """
    while True:
        try:
            # create a json payload with the current boat status
            status_payload = json.dumps({
                "identifier": config.identifier,
                "streamdata": streamdata,
                "logdata": logdata,
                "deletelogstatus": deletelogstatus
            })
            mqtt_client.publish(MQTT_BoatStatus, status_payload)
            logger.debug("datamanager_publish_boatstatus_published boat status: %s", status_payload)
        except Exception as e:
            logger.error("datamanager_publish_boatstatus_error publishing boat status: %s", e)
        time.sleep(2)


def init_db():
    """
    initializes the sqlite database and creates the logdata table if it doesn't exist.
    """
    global conn, cursor  # use globals to modify the connection and cursor outside this function

    db_dir = os.path.dirname(DB_FILE)
    if not os.path.exists(db_dir):
        try:
            # create the directory for the database if it does not exist
            os.makedirs(db_dir)
            logger.debug("datamanager_init_db_created directory: %s", db_dir)
        except Exception as e:
            logger.error("datamanager_init_db_error creating directory: %s", e)
            return None

    try:
        # open a persistent connection to the sqlite database with multithreading support
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
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
            wifi_signal_strength TEXT,
            acc_x REAL,
            acc_y REAL,
            acc_z REAL,
            gyro_x REAL,
            gyro_y REAL,
            gyro_z REAL,
            pitch REAL,
            roll REAL,
            mag_x REAL,
            mag_y REAL,
            mag_z REAL,
            heading REAL
            )
        ''')
        conn.commit()
        logger.debug("datamanager_init_db_database initialized at %s", DB_FILE)
    except Exception as e:
        logger.error("datamanager_init_db_error initializing database: %s", e)


def log_data_to_db():
    """
    continuously pulls data from the queue and logs it to the database
    if the data has validtime true and logdata is enabled.
    """
    while True:
        # block until data is available in the queue
        data = data_queue.get()

        # log data only if validtime is true and logging is enabled
        if data.get('validtime', False) and logdata:
            # replace empty strings with None for proper database insertion
            for key, value in data.items():
                if value == '':
                    data[key] = None

            try:
                cursor.execute('''
                    INSERT INTO logdata (
                        datetime, status, lat, long, SOG, COG, fixQ, nSat, HDOP, alt, id, validtime,
                        batvolt, batperc, wifi_conn, wifi_signal_strength,
                        acc_x, acc_y, acc_z,
                        gyro_x, gyro_y, gyro_z,
                        pitch, roll, 
                        mag_x, mag_y, mag_z, heading
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data.get('datetime'),
                    data.get('status'),
                    data.get('lat'),
                    data.get('long'),
                    data.get('SOG'),
                    data.get('COG'),
                    data.get('fixQ'),
                    data.get('nSat'),
                    data.get('HDOP'),
                    data.get('alt'),
                    data.get('id'),
                    data.get('validtime'),
                    data.get('batvolt'),
                    data.get('batperc'),
                    data.get('wifi_conn'),
                    data.get('wifi_signal_strength'),
                    data.get('acc_x'),
                    data.get('acc_y'),
                    data.get('acc_z'),
                    data.get('gyro_x'),
                    data.get('gyro_y'),
                    data.get('gyro_z'),
                    data.get('pitch'),
                    data.get('roll'),
                    data.get('mag_x'),
                    data.get('mag_y'),
                    data.get('mag_z'),
                    data.get('heading')
                ))
                conn.commit()
                logger.debug("datamanager_log_data_to_db_logged data to database: %s", data)
            except Exception as e:
                logger.error("datamanager_log_data_to_db_error inserting data into database: %s", e)
        else:
            logger.debug("datamanager_log_data_to_db_skipping data (validtime=%s, logdata=%s)", data.get('validtime'), logdata)

        # mark the queue task as done
        data_queue.task_done()


def handle_delete_log():
    """
    continuously monitors the global deletelog flag.
    when deletelog is true:
      - set logdata to false,
      - set deletelogstatus to "deleting",
      - delete all rows from the logdata table,
      - update deletelogstatus to "deleted",
      - wait until deletelog is set back to false,
      - then reset deletelogstatus and restore logdata.
    """
    global deletelogstatus, logdata, deletelog

    while True:
        # check if deletion of log data is requested
        if deletelog:
            # disable logging and mark deletion process as started
            logdata = False
            deletelogstatus = "deleting"

            try:
                # delete all rows in the logdata table
                cursor.execute("DELETE FROM logdata")
                conn.commit()
                deletelogstatus = "deleted"
                logger.debug("datamanager_handle_delete_log_all log data deleted from the database")
            except Exception as e:
                deletelogstatus = f"Error: {e}"
                logger.error("datamanager_handle_delete_log_error deleting log data: %s", e)

            # wait until the deletelog flag is reset to false
            while deletelog:
                time.sleep(1)

            # reset deletion status and re-enable logging
            deletelogstatus = "-"
            logdata = True

        time.sleep(1)


# initialize database connection on module import if not already done
if conn is None:
    init_db()
