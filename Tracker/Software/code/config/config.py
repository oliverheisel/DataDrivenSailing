# pin configuration and device settings

# tracker identifier
identifier = "boat2"

# debug logging control (set to false to disable debug logging)
log_debug = True

# hub wifi credentials
ssid = "hub"
password = "SailingBoat#7xTq9!"

# i2c addresses for sensors (specified as hexadecimal strings)
gps_i2c = "0x42"
battery_i2c = "0x36"
gyroacc_i2c = "0x6b"
mag_i2c = "0x30"

# device orientation configuration
# 1: mounted flat on the boat (top facing the sky)
# 2: mounted to the front wall (top facing backwards)
# 3: mounted to the back wall (top facing forwards)
device_orientation = 1

# led module configuration (using broadcom pin numbering)
led_r = 20
led_g = 12
led_b = 16

# mqtt broker settings
mqtt_broker = "hub.local"
mqtt_port = 1883
mqtt_boatlive = "boatlive"
mqtt_boatcontrol = "boatcontrol"
mqtt_boatstatus = "boatstatus"
