import os, time, queue, threading, logging, importlib
import errordebuglogger as edl

from config import config
from modules import gps, imu, mag, battery, led
import datamanager

# ---------------------------------------------------------------------------
# Debug logging
# ---------------------------------------------------------------------------
if hasattr(edl, "set_level"):
    edl.set_level(os.getenv("LOGLEVEL", "INFO"))
logger = edl.get_logger(__name__) if hasattr(edl, "get_logger") \
         else logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Device-specific sensor sets
# ---------------------------------------------------------------------------
SENSOR_SETS = {
    "boat": ["gps", "imu", "bat", "led", "wifi"],
    "buoy": ["gps", "bat", "led", "wifi"],
    "hub":  ["gps", "led", "wind"],
}
try:
    ACTIVE_SENSORS = set(SENSOR_SETS[config.device_type])
except KeyError:
    raise SystemExit(f"Unknown device_type '{config.device_type}'")

# ---------------------------------------------------------------------------
# Optional driver loader (e.g. wind sensor → requires pyserial)
# ---------------------------------------------------------------------------
def _import_driver(modname: str):
    try:
        return importlib.import_module(f"modules.{modname}")
    except ModuleNotFoundError as exc:
        logger.info("Optional driver '%s' not available: %s", modname, exc)
        return None

wind_drv = _import_driver("wind_calypsomini") or _import_driver("wind")

# ---------------------------------------------------------------------------
# Globals / settings
# ---------------------------------------------------------------------------
snap_q: queue.SimpleQueue = queue.SimpleQueue()
new_ev:  threading.Event  = threading.Event()

battery_read_interval = 1 / getattr(config, "battery_read_freq", 0.5)
interim_freq          = 1/ getattr(config, "interim_freq", 0.1)

# ---------------------------------------------------------------------------
# Helper: Wi-Fi status
# ---------------------------------------------------------------------------
def _read_wifi():
    if "wifi" not in ACTIVE_SENSORS:
        return False, None
    try:
        with open("/sys/class/net/wlan0/operstate") as f:
            conn = (f.read().strip() == "up")
        rssi = None
        if conn:
            with open("/proc/net/wireless") as f:
                for line in f.readlines()[2:]:
                    if "wlan0:" in line:
                        rssi = int(float(line.split()[3]))
                        break
    except Exception as e:
        logger.error("wifi read failed: %s", e)
        conn, rssi = False, None
    return conn, rssi

# ---------------------------------------------------------------------------
# Producer – GPS thread + sensor fusion
# ---------------------------------------------------------------------------
def gps_captain() -> None:
    last_gps_ts: str | None = None
    last_bat: dict | None = None
    next_bat_due = 0.0
    last_interim = 0.0

    gps.init_gps()
    threading.Thread(target=gps.read_gps, daemon=True).start()

    while True:
        fix = gps.get_data()
        now = time.monotonic()

        # --------------------- NO GPS FIX YET -------------------------- #
        if not fix or fix.get("datetime") is None:
            if now - last_interim >= interim_freq:
                wifi_conn, wifi_rssi = _read_wifi()

                snapshot = {
                    "ts_monotonic": now,
                    "id": config.identifier,
                    "validtime": False,
                    "status": "V",
                }
                if "gps" in ACTIVE_SENSORS:
                    snapshot["gps"] = fix
                if "imu" in ACTIVE_SENSORS:
                    snapshot["imu"] = imu.get_data()
                if "mag" in ACTIVE_SENSORS:
                    snapshot["mag"] = mag.get_data()
                if "bat" in ACTIVE_SENSORS:
                    try:
                        last_bat = battery.get_battery_json()
                    except Exception as e:
                        logger.error("battery read failed: %s", e)
                        last_bat = {}
                    snapshot["bat"] = last_bat
                if "wind" in ACTIVE_SENSORS and wind_drv:
                    heading_val = (
                        snapshot.get("mag", {}) or {}
                    ).get("heading", 0) or 0
                    snapshot["wind"] = wind_drv.get_data(heading_val)

                snapshot["wifi_conn"], snapshot["wifi_rssi"] = (
                    wifi_conn,
                    wifi_rssi,
                )

                snap_q.put(snapshot)
                new_ev.set()
                last_interim = now
            time.sleep(0.2)
            continue
        # --------------------------------------------------------------- #

        gps_ts = fix["datetime"]
        if gps_ts == last_gps_ts:
            time.sleep(0.02)
            continue
        last_gps_ts = gps_ts

        # periodic battery read
        if "bat" in ACTIVE_SENSORS and now >= next_bat_due:
            try:
                last_bat = battery.get_battery_json()
            except Exception as e:
                logger.error("battery read failed: %s", e)
                last_bat = {}
            next_bat_due = now + battery_read_interval

        wifi_conn, wifi_rssi = _read_wifi()

        snapshot = {
            "ts_monotonic": now,
            "id": config.identifier,
            "validtime": True,
            "status": "A",
        }
        if "gps" in ACTIVE_SENSORS:
            snapshot["gps"] = fix
        if "imu" in ACTIVE_SENSORS:
            snapshot["imu"] = imu.get_data()
        if "mag" in ACTIVE_SENSORS:
            snapshot["mag"] = mag.get_data()
        if "bat" in ACTIVE_SENSORS:
            snapshot["bat"] = last_bat
        if "wind" in ACTIVE_SENSORS and wind_drv:
            heading_val = (
                snapshot.get("mag", {}) or {}
            ).get("heading", 0) or 0
            snapshot["wind"] = wind_drv.get_data(heading_val)

        snapshot["wifi_conn"], snapshot["wifi_rssi"] = wifi_conn, wifi_rssi

        snap_q.put(snapshot)
        new_ev.set()

# ---------------------------------------------------------------------------
# Consumer – upload / log
# ---------------------------------------------------------------------------
def mainloop() -> None:
    while True:
        new_ev.wait(); new_ev.clear()
        snap = snap_q.get_nowait()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("merged snapshot: %s", snap)
        datamanager.datatransfer(snap, snap.get("wifi_conn"))

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def main() -> None:
    threading.Thread(target=datamanager.mqtt_loop,          daemon=True).start()
    threading.Thread(target=datamanager.publish_boatstatus, daemon=True).start()
    threading.Thread(target=datamanager.log_data_to_db,     daemon=True).start()
    threading.Thread(target=datamanager.handle_delete_log,  daemon=True).start()
    threading.Thread(target=led.led_loop,                   daemon=True).start()
    threading.Thread(target=gps_captain,                    daemon=True).start()
    mainloop()

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
