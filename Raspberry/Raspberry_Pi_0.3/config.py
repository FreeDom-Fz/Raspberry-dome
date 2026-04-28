# Raspberry Pi Monitoring Controller Configuration

# Logger Configuration
LOG_CONFIG_SCHEDULED = {
    'log_path': '/home/pi/Raspberry_Pi/logs/scheduled_tasks.log',
    'max_bytes': 5 * 1024 * 1024,
    'backup_count': 5,
    'format': '%(asctime)s - [SCHEDULED] - %(levelname)s - %(message)s'
}

LOG_CONFIG_MQTT = {
    'log_path': '/home/pi/Raspberry_Pi/logs/mqtt_tasks.log',
    'max_bytes': 5 * 1024 * 1024,
    'backup_count': 5,
    'format': '%(asctime)s - [MQTT] - %(levelname)s - %(message)s'
}

# MQTT Configuration
MQTT_BROKER = 'broker.emqx.io'
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_TOPIC_SUBSCRIBE = 'test/cheshi'
MQTT_TOPIC_PUBLISH = 'test/longge'
MQTT_TOPIC_RESPONSE = 'test/abc'

# Image Configuration
LOCAL_DIR = '/home/pi/Raspberry_Pi/Local_image'
USE_TIMESTAMP = True

# Sensor Configuration - DHT11
READ_TIMEOUT = 2
MIN_TEMP = -40
MAX_TEMP = 85
MIN_HUMI = 0
MAX_HUMI = 100

# Sensor Configuration - Soil
SOIL_PIN = 17
READ_DELAY = 1
SOIL_WET_LEVEL = 0
SOIL_DRY_LEVEL = 1

# SFTP Configuration
SERVER_IP = '39.106.159.23'
SERVER_PORT = 22
USERNAME = 'root'
PASSWORD = 'LjJ@0809!12'
REMOTE_DIR = '/ShujuTp/'