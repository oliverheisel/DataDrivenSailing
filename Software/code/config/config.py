## Configuration file for the BoatTracker, BuoyTracker and Hub

# Indentiefier - use the same as you used in the Os settings (e.g. boat1, buoy1, hub)
identifier = "hub"

# device type
device_type = "hub"  # options: "boat", "buoy", "hub"

# ---------------------------------------------------------------------------
# Debug logging
# ---------------------------------------------------------------------------
# debug logging control (set to false to disable debug logging)
log_debug = True


# ---------------------------------------------------------------------------
# Device orientation
# ---------------------------------------------------------------------------
# 1: default - mounted flat on the boat (top facing the sky)
# 2: mounted to the front wall (top facing backwards)
# 3: mounted to the back wall (top facing forwards)
device_orientation = 1


# ---------------------------------------------------------------------------
# Update-rates / damping, filtering
# ---------------------------------------------------------------------------
livedata_freq = 10     # Hz   – max live data updates per second
interim_freq = 10   # Hz   – interim data updates per second (before GPS fix)
battery_read_freq  = 2.0    # s – time between battery measurements

GPS_UPDATE = 10   # HZ - supported: 1, 2, 5, 10, 15, 20, 25
GPS_MAX_SPEED_KNOTS = 20.0  # knots – max speed for GPS filtering and validation


# ---------------------------------------------------------------------------
# i2c bus settings, GPIO configuration and MQTT settings
# ---------------------------------------------------------------------------

# i2c addresses for sensors (specified as hexadecimal strings)
gps_i2c = "0x42"
battery_i2c = "0x36"
imu_i2c = "0x6b"
mag_i2c = "0x30"

# led module configuration (using broadcom pin numbering)
led_r = 20
led_g = 16
led_b = 12

# mqtt broker settings
mqtt_broker = "hub.local"
mqtt_port = 1883
mqtt_boatlive = "boatlive"
mqtt_boatcontrol = "boatcontrol"
mqtt_boatstatus = "boatstatus"

mqtt_buoylive = "buoylive"
mqtt_buoycontrol = "buoycontrol"
mqtt_buoystatus = "buoystatus"

mqtt_hublive = "hublive"
mqtt_hubcontrol = "hubcontrol"
mqtt_hubstatus = "hubstatus"