# ---------------------------------------------------------------------------
# datamanager.py – all non-sensor I/O
# ---------------------------------------------------------------------------
# • MQTT streaming, control & status
# • SQLite logging
# • Delete-log handling
#
# 100 % Funktionsparität zum ursprünglichen Skript:
#   – dieselben Flags (streamdata, logdata, deletelog, deletelogstatus)
#   – identische Logmeldungen und Zeitabstände
#   – identisches DB-Schema (plus zwei optionale Wind-Spalten)
#
# Ergänzungen:
#   • MQTT-Topics erhalten einen Prefix aus config.device_type
#     (boat / buoy / hub) -> boatlive / buoycontrol / …
#   • _flatten_all() verarbeitet jetzt auch „imu“
#   • DB wird bei Löschvorgang vollständig entfernt und neu erstellt
#   • Schreibfehler in DB werden über `log_db_error` gemeldet
#   • Queue wird beim Löschen geleert
# ---------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import time
import uuid

import paho.mqtt.client as mqtt
from config import config

# ---------------------------------------------------------------------------
# Debug logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MQTT configuration
# ---------------------------------------------------------------------------
MQTT_BROKER = config.mqtt_broker
MQTT_PORT   = config.mqtt_port

_prefix      = config.device_type.lower()           # boat | buoy | hub
MQTT_LIVE    = f"{_prefix}live"
MQTT_CONTROL = f"{_prefix}control"
MQTT_STATUS  = f"{_prefix}status"

# ---------------------------------------------------------------------------
# Runtime flags & shared state
# ---------------------------------------------------------------------------
streamdata        = True         # publish snapshots on *_live
logdata           = True         # write snapshots to SQLite
deletelog         = False        # request flag (set via MQTT control)
deletelogstatus   = "-"          # "-", "deleting", "deleted", "Error: …"
log_db_error      = False        # raised when INSERT/commit fails

data_queue: queue.Queue = queue.Queue(maxsize=512)

wifi_conn   = False              # last Wi-Fi state
latest_data: dict = {}           # last flattened snapshot

# ---------------------------------------------------------------------------
# MQTT client (singleton)
# ---------------------------------------------------------------------------
mqtt_client = mqtt.Client(client_id=str(uuid.uuid4()), clean_session=True)

# ---------------------------------------------------------------------------
# Helper – flatten nested blocks
# ---------------------------------------------------------------------------
def _flatten_all(data: dict) -> None:
    """Promote sensor sub-dicts to top level without renaming keys."""
    for blk in ("gps", "gyro", "imu", "mag", "bat", "wind"):
        sub = data.pop(blk, None)
        if isinstance(sub, dict):
            data.update(sub)

# ---------------------------------------------------------------------------
# Data transfer from main.py
# ---------------------------------------------------------------------------
_last_publish = 0.0        # monotonic time for 10 Hz throttle

def datatransfer(snapshot: dict, wifi_status: bool) -> None:
    """
    * Flatten snapshot
    * Queue for DB logger
    * Publish (throttled) on MQTT_LIVE
    """
    global wifi_conn, latest_data, _last_publish

    _flatten_all(snapshot)

    if "wifi_signal_strength" not in snapshot and "wifi_rssi" in snapshot:
        snapshot["wifi_signal_strength"] = snapshot.pop("wifi_rssi")

    wifi_conn   = wifi_status
    latest_data = snapshot
    data_queue.put(snapshot)

    if streamdata and time.time() - _last_publish >= 0.1:
        _last_publish = time.time()
        try:
            mqtt_client.publish(MQTT_LIVE, json.dumps(snapshot, default=str))
        except Exception as exc:
            logger.error("MQTT publish error: %s", exc)

# ---------------------------------------------------------------------------
# MQTT background loop – listens for control JSON
# ---------------------------------------------------------------------------
def mqtt_loop() -> None:
    def on_connect(client, _ud, _fl, rc):
        if rc == 0:
            client.subscribe(MQTT_CONTROL)
            logger.debug("MQTT connected, subscribed control")
        else:
            logger.debug("MQTT connect rc=%s", rc)

    def on_message(_c, _ud, msg):
        global streamdata, logdata, deletelog
        try:
            if msg.topic != MQTT_CONTROL:
                return
            cfg = json.loads(msg.payload.decode(errors="ignore"))
            streamdata = cfg.get("streamdata", streamdata)
            logdata    = cfg.get("logdata",    logdata)
            deletelog  = cfg.get("deletelog",  deletelog)
            logger.debug("Control: stream=%s log=%s delete=%s",
                         streamdata, logdata, deletelog)
        except Exception as exc:
            logger.error("MQTT control parse error: %s", exc)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_forever()
        except Exception as exc:
            logger.error("MQTT connection error: %s", exc)
            time.sleep(5)

# ---------------------------------------------------------------------------
# Periodic status publisher (2 s)
# ---------------------------------------------------------------------------
def publish_boatstatus() -> None:
    while True:
        try:
            status_json = json.dumps({
                "identifier":      config.identifier,
                "streamdata":      streamdata,
                "logdata":         logdata,
                "deletelogstatus": deletelogstatus,
                "log_db_error":    log_db_error,
                "batperc":         latest_data.get("batperc"),
            })
            mqtt_client.publish(MQTT_STATUS, status_json)
            logger.debug("Boat status sent")
        except Exception as exc:
            logger.error("Boat status error: %s", exc)
        time.sleep(2)

# ---------------------------------------------------------------------------
# SQLite – file path & init
# ---------------------------------------------------------------------------
DB_FILE = f"/home/globaladmin/data/datalog_{config.identifier}.db"
conn, cursor = None, None

def init_db() -> None:
    """Open DB and, if it does not yet exist, create the complete schema."""
    global conn, cursor
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

    need_create = not os.path.exists(DB_FILE)

    conn   = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()

    if need_create:
        cursor.execute("""
        CREATE TABLE logdata (
            datetime TEXT, status TEXT,
            lat REAL, long REAL, SOG TEXT, COG TEXT,
            fixQ TEXT, nSat TEXT, HDOP TEXT, alt TEXT,
            id TEXT, validtime BOOLEAN,
            -- battery
            batvolt REAL, batperc REAL,
            -- Wi-Fi
            wifi_conn BOOLEAN, wifi_signal_strength TEXT,
            -- IMU
            acc_x REAL, acc_y REAL, acc_z REAL,
            gyro_x REAL, gyro_y REAL, gyro_z REAL,
            pitch REAL, roll REAL,
            -- magnetometer
            mag_x REAL, mag_y REAL, mag_z REAL, heading REAL,
            -- wind sensor (exact names from main.py)
            w_speed REAL, w_angle REAL,
            w_speed_kts REAL, true_wind_dir REAL
        )
        """)
        conn.commit()
        logger.debug("SQLite created: %s", DB_FILE)
    else:
        logger.debug("SQLite opened:  %s", DB_FILE)

# ---------------------------------------------------------------------------
# Logger thread – write queued snapshots
# ---------------------------------------------------------------------------
def log_data_to_db() -> None:
    global log_db_error
    while True:
        data = data_queue.get()
        _flatten_all(data)

        if "wifi_signal_strength" not in data and "wifi_rssi" in data:
            data["wifi_signal_strength"] = data.pop("wifi_rssi")

        if data.get("validtime") and logdata:
            for k, v in list(data.items()):
                if v == "":
                    data[k] = None
            try:
                cursor.execute("""
                    INSERT INTO logdata (
                        datetime,status,lat,long,SOG,COG,fixQ,nSat,HDOP,alt,id,validtime,
                        batvolt,batperc,
                        wifi_conn,wifi_signal_strength,
                        acc_x,acc_y,acc_z,
                        gyro_x,gyro_y,gyro_z,
                        pitch,roll,
                        mag_x,mag_y,mag_z,heading,
                        w_speed,w_angle,w_speed_kts,true_wind_dir
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    data.get("datetime"), data.get("status"),
                    data.get("lat"),      data.get("long"),
                    data.get("SOG"),      data.get("COG"),
                    data.get("fixQ"),     data.get("nSat"),
                    data.get("HDOP"),     data.get("alt"),
                    data.get("id"),       data.get("validtime"),
                    data.get("batvolt"),  data.get("batperc"),
                    data.get("wifi_conn"),data.get("wifi_signal_strength"),
                    data.get("acc_x"),    data.get("acc_y"),  data.get("acc_z"),
                    data.get("gyro_x"),   data.get("gyro_y"), data.get("gyro_z"),
                    data.get("pitch"),    data.get("roll"),
                    data.get("mag_x"),    data.get("mag_y"),  data.get("mag_z"),
                    data.get("heading"),
                    data.get("w_speed"),      data.get("w_angle"),
                    data.get("w_speed_kts"),  data.get("true_wind_dir"),
                ))
                conn.commit()
                logger.debug("DB insert OK")
                log_db_error = False
            except Exception as exc:
                logger.error("SQLite insert error: %s", exc)
                log_db_error = True
        else:
            logger.debug("DB skip (validtime=%s logdata=%s)",
                         data.get("validtime"), logdata)

        data_queue.task_done()

# ---------------------------------------------------------------------------
# Delete-log thread – delete DB file and reinit
# ---------------------------------------------------------------------------
def handle_delete_log() -> None:
    global deletelog, deletelogstatus, logdata, conn, cursor
    while True:
        if deletelog:
            logdata = False
            deletelogstatus = "deleting"
            try:
                # Clear queue
                while not data_queue.empty():
                    data_queue.get_nowait()
                    data_queue.task_done()

                # Close and remove DB
                if conn:
                    conn.close()
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)

                # Re-init
                init_db()
                deletelogstatus = "deleted"
                logger.debug("Database deleted and reinitialized")
            except Exception as exc:
                deletelogstatus = f"Error: {exc}"
                logger.error("Delete-log error: %s", exc)

            # Wait until external control clears the flag
            while deletelog:
                time.sleep(1)

            deletelogstatus = "-"
            logdata = True
        time.sleep(1)

# ---------------------------------------------------------------------------
# Module initialisation
# ---------------------------------------------------------------------------
if conn is None:
    init_db()
