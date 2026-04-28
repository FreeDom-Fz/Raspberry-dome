# -*- coding: utf-8 -*-
import paho.mqtt.client as mqtt
import os
import time
import datetime
import subprocess
import adafruit_dht
import board
import RPi.GPIO as GPIO
import paramiko
import threading
from config import *
from logger import get_logger

logger = get_logger(LOG_CONFIG_MAIN2)

# ====================== Camera =======================
def take_photo():
    if USE_TIMESTAMP:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Gctp_Element-{timestamp}.jpg"
    else:
        filename = "Gctp.jpg"

    local_path = os.path.join(LOCAL_DIR, filename)
    os.makedirs(LOCAL_DIR, exist_ok=True)

    try:
        subprocess.run([
            "rpicam-still",
            "-o", local_path,
            "--width", "1920",
            "--height", "1080",
            "--timeout", "1000"
        ], check=True)
        logger.info(f"Photo saved: {local_path}")
        return local_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Capture failed: {e}")
        return None

# ====================== DHT11 =======================
dht_device = adafruit_dht.DHT11(board.D4)

def read_sensor():
    try:
        start_time = time.time()
        temp = None
        humi = None
        while time.time() - start_time < READ_TIMEOUT:
            try:
                temp = dht_device.temperature
                humi = dht_device.humidity
                if temp is not None and humi is not None:
                    break
            except RuntimeError:
                time.sleep(0.1)
                continue

        if temp is None or humi is None:
            logger.warning("DHT11 read timeout")
            return None, None

        logger.info(f"Read success: {temp:.1f} {humi:.1f}%")
        return temp, humi

    except Exception as e:
        logger.critical(f"DHT11 error: {e}")
        return None, None

# ====================== Soil Sensor =======================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(SOIL_PIN, GPIO.IN)

def read_soil_sensor():
    try:
        level = GPIO.input(SOIL_PIN)
        if level == SOIL_WET_LEVEL:
            logger.info("Soil: Wet")
            return "Wet"
        else:
            logger.info("Soil: Dry")
            return "Dry"
    except Exception as e:
        logger.error(f"Soil sensor error: {str(e)}")
        return "Unknown"

# ====================== Upload =======================
def upload_file(local_path):
    if not local_path:
        logger.warning("No photo to upload")
        return None

    try:
        transport = paramiko.Transport((SERVER_IP, 22))
        transport.connect(username=USERNAME, password=PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)
        remote_path = os.path.join(REMOTE_DIR, os.path.basename(local_path))
        sftp.put(local_path, remote_path)
        sftp.close()
        transport.close()
        logger.info(f"Photo uploaded: {remote_path}")
        return remote_path
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return None

# ====================== Task Worker =======================
def do_work(client):
    photo = take_photo()
    temp, humi = read_sensor()
    soil = read_soil_sensor()
    remote_path = upload_file(photo)
    
    result_msg = f"Photo:{remote_path},Temp:{temp},Humi:{humi},Soil:{soil}"
    client.publish("test/longge", result_msg)
    client.publish("test/abc", "success")
    logger.info("Task finished, response sent")

# ====================== MQTT Callback =======================
def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8").strip()
    logger.info(f"Command received: {payload}")
    threading.Thread(target=do_work, args=(client,)).start()

# ====================== MQTT Main =======================
if __name__ == "__main__":
    client = mqtt.Client()
    client.on_message = on_message

    try:
        client.connect("broker.emqx.io", 1883, 60)
        client.subscribe("test/cheshi")
        logger.info("MQTT started, waiting command...")
        client.loop_forever()
    except Exception as e:
        logger.error(f"MQTT error: {e}")