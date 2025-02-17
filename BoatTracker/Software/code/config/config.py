
## Pin configuration

# tracker identifier
identifier = "boat1"

# hub wifi credentials
ssid = "hub"
password = "SailingBoat#7xTq9!"

# i2c address
gps_i2c = "0x42"
battery_i2c = "0x36"
mag_i2c = "0x30"
gyro_i2c = "0x6b"

# led module
led_r = 20
led_g = 12
led_b = 16

mqtt_broker = "hub.local"  # Change this to your MQTT broker IP or hostname
mqtt_port = 1883
mqtt_boatlive = "boatlive"
mqtt_boatcontrol = "boatcontrol"
mqtt_boatstatus = "boatstatus" 

