import time
import paho.mqtt.client as mqtt
import json
import logging
import uuid
import queue
from config import config

# set up logger
logger = logging.getLogger(__name__)

# MQTT broker configuration
MQTT_BROKER = config.mqtt_broker
MQTT_PORT = config.mqtt_port
MQTT_LiveData = config.mqtt_hublive

# control topic configuration
MQTT_Control = getattr(config, "mqtt_control", "default/control")

# create a unique MQTT client id
MQTT_CLIENT_ID = f"{config.identifier}_{uuid.uuid4().hex[:8]}"
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)

# global variables for data management
latest_data = {}
data_queue = queue.Queue()

def replace_none_with_empty_string(data):
    """
    recursively replaces all None values in a dictionary with an empty string.
    """
    if isinstance(data, dict):
        return {k: replace_none_with_empty_string(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_none_with_empty_string(i) for i in data]
    elif data is None:
        return ""
    return data

def datatransfer(data):
    """
    publishes sensor data to the MQTT broker.
    also pushes data to the database queue.
    converts data into valid JSON format before sending.
    """
    global latest_data
    latest_data = data

    try:
        # convert None values to empty strings
        cleaned_data = replace_none_with_empty_string(data)
        
        # convert data to JSON (converts None to null, etc.)
        json_data = json.dumps(cleaned_data, default=str)
        data_queue.put(cleaned_data)
        try:
            mqtt_client.publish(MQTT_LiveData, json_data)  # publish the JSON-formatted data
            logger.debug("datatransfer_published data: %s", json_data)
        except Exception as e:
            logger.error("datatransfer_error publishing data: %s", str(e))
    except Exception as e:
        logger.error("datatransfer_error converting data to JSON: %s", str(e))

def mqtt_loop():
    """
    manages the MQTT connection, handles automatic reconnections,
    subscribes to the control topic, and processes incoming messages.
    """
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(MQTT_Control)
            logger.debug("mqtt_loop_connected to MQTT broker and subscribed to control topic")
        else:
            logger.error("mqtt_loop_failed to connect, return code %d", rc)

    def on_message(client, userdata, msg):
        try:
            message = msg.payload.decode(errors='ignore')
            if msg.topic == MQTT_Control:
                # process control message if needed
                config_data = json.loads(message)
                logger.debug("mqtt_loop_received control message: %s", message)
        except json.JSONDecodeError as e:
            logger.error("mqtt_loop_error decoding JSON message: %s", str(e))
        except Exception as e:
            logger.error("mqtt_loop_error processing message: %s", str(e))

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_forever()
        except Exception as e:
            logger.error("mqtt_loop_MQTT connection failed: %s. Retrying in 5 seconds...", str(e))
            time.sleep(5)
