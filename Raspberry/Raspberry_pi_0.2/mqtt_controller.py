# -*- coding: utf-8 -*-
import os
import time
import datetime
import subprocess
import adafruit_dht
import board
import RPi.GPIO as GPIO
import paramiko
import paho.mqtt.client as mqtt
import threading
from config import *
from logger import get_logger

logger = get_logger(LOG_CONFIG_MAIN1)

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

_KQ_LOCK = threading.Lock()
_KQ_INITIALIZED = False
dht_device = None

def sensor_init_kq():
    global _KQ_INITIALIZED, dht_device
    if _KQ_INITIALIZED:
        logger.warning("DHT22 initialized already")
        return
    try:
        dht_device = adafruit_dht.DHT11(board.D4)
        _KQ_INITIALIZED = True
        logger.info("DHT22 init success")
    except Exception as e:
        logger.error(f"DHT22 init error: {e}")

def sensor_cleanup_kq():
    global _KQ_INITIALIZED, dht_device
    if not _KQ_INITIALIZED:
        return
    try:
        dht_device.exit()
    except:
        pass
    _KQ_INITIALIZED = False
    logger.info("DHT11 cleaned up")

def read_sensor():
    global _KQ_INITIALIZED, dht_device
    if not _KQ_INITIALIZED or dht_device is None:
        logger.error("DHT11 not initialized")
        return None, None

    if not _KQ_LOCK.acquire(blocking=False):
        logger.warning("DHT11 busy")
        return None, None

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

        if not (MIN_TEMP <= temp <= MAX_TEMP):
            logger.error(f"Temperature abnormal: {temp}")
            return None, None
        if not (MIN_HUMI <= humi <= MAX_HUMI):
            logger.error(f"Humidity abnormal: {humi}")
            return None, None

        logger.info(f"Read success: {temp:.1f} {humi:.1f}%")
        return temp, humi

    except Exception as e:
        logger.critical(f"DHT11 error: {e}")
        sensor_cleanup_kq()
        return None, None
    finally:
        _KQ_LOCK.release()

_TU_INITIALIZED = False

def sensor_init_tu():
    global _TU_INITIALIZED
    if _TU_INITIALIZED:
        logger.warning("Soil sensor initialized already")
        return
    
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(SOIL_PIN, GPIO.IN)
    
    _TU_INITIALIZED = True
    logger.info("Soil sensor init success")

def sensor_cleanup_tu():
    global _TU_INITIALIZED
    if not _TU_INITIALIZED:
        return
    
    try:
        GPIO.cleanup(SOIL_PIN)
    except Exception:
        pass
    _TU_INITIALIZED = False
    logger.info("Soil sensor cleaned up")

def read_soil_sensor():
    global _TU_INITIALIZED
    if not _TU_INITIALIZED:
        logger.error("Soil sensor not initialized")
        return "Unknown"

    try:
        level = GPIO.input(SOIL_PIN)
        if level == SOIL_WET_LEVEL:
            logger.info("Soil: Wet")
            return "Wet"
        else:
            logger.info("Soil: Dry")
            return "Dry"
    except Exception as e:
        logger.critical(f"Soil sensor error: {str(e)}")
        return "Unknown"

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

client = mqtt.Client()
try:
    client.connect("broker.emqx.io", 1883, 60)
    logger.info("MQTT connected")
except:
    logger.error("MQTT connect failed")

if __name__ == "__main__":
    logger.info("Program started")
    sensor_init_kq()
    sensor_init_tu()

    try:
        while True:
            try:
                photo = take_photo()
                temp, humi = read_sensor()
                soil = read_soil_sensor()
                remote_path = upload_file(photo)
                
                msg = f"Photo:{remote_path},Temp:{temp},Humi:{humi},Soil:{soil}"
                client.publish("test/longge", msg)
                logger.info(f"MQTT sent: {msg}")

            except Exception as e:
                logger.error(f"Loop error: {e}")

            time.sleep(3600)

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        sensor_cleanup_kq()
        sensor_cleanup_tu()
        logger.info("All resources released")
