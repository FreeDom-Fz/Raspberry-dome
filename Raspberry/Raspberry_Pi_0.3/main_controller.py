# -*- coding: utf-8 -*-
# Raspberry Pi Monitoring Controller
# Features:
# 1. Scheduled Task: Automatically collect sensor data and upload every hour
# 2. MQTT Response: Receive remote commands, execute sensor operations and return results
# 3. Unified sensor management to avoid access conflicts

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

# ====================== Logger Configuration =======================
# Create two independent loggers
# scheduled_logger: for scheduled task logging
# mqtt_logger: for MQTT response task logging
scheduled_logger = get_logger(LOG_CONFIG_SCHEDULED)
mqtt_logger = get_logger(LOG_CONFIG_MQTT)

# ====================== Sensor Configuration =======================
# Thread locks: protect sensor resources, prevent concurrent access conflicts
_KQ_LOCK = threading.Lock()  # DHT11 temperature and humidity sensor lock
_TU_LOCK = threading.Lock()  # Soil humidity sensor lock

# Sensor initialization status
_KQ_INITIALIZED = False
_TU_INITIALIZED = False
dht_device = None

# ====================== DHT11 Temperature & Humidity Sensor =======================
def sensor_init_kq():
    # Initialize DHT11 temperature and humidity sensor
    # Use global lock to protect initialization process
    global _KQ_INITIALIZED, dht_device
    if _KQ_INITIALIZED:
        return True
    try:
        dht_device = adafruit_dht.DHT11(board.D4)
        _KQ_INITIALIZED = True
        scheduled_logger.info("[Sensor] DHT11 init success")
        mqtt_logger.info("[Sensor] DHT11 init success")
        return True
    except Exception as e:
        scheduled_logger.error(f"[Sensor] DHT11 init error: {e}")
        mqtt_logger.error(f"[Sensor] DHT11 init error: {e}")
        return False

def sensor_cleanup_kq():
    # Clean up DHT11 sensor resources
    # Release GPIO resources occupied by the sensor
    global _KQ_INITIALIZED, dht_device
    if not _KQ_INITIALIZED:
        return
    try:
        if dht_device:
            dht_device.exit()
    except:
        pass
    _KQ_INITIALIZED = False
    scheduled_logger.info("[Sensor] DHT11 cleaned up")
    mqtt_logger.info("[Sensor] DHT11 cleaned up")

def read_sensor():
    # Read DHT11 temperature and humidity sensor data
    # Use thread lock to protect reading process, prevent concurrent access
    # return: (temperature, humidity) tuple, returns (None, None) on failure
    global _KQ_INITIALIZED, dht_device
    if not _KQ_INITIALIZED or dht_device is None:
        return None, None

    # Try to acquire lock, non-blocking mode
    if not _KQ_LOCK.acquire(blocking=False):
        return None, None

    try:
        start_time = time.time()
        temp = None
        humi = None
        # Continuously try to read within timeout period
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
            return None, None

        # Data validity check
        if not (MIN_TEMP <= temp <= MAX_TEMP):
            return None, None
        if not (MIN_HUMI <= humi <= MAX_HUMI):
            return None, None

        return temp, humi

    except Exception as e:
        scheduled_logger.error(f"[Sensor] DHT11 error: {e}")
        mqtt_logger.error(f"[Sensor] DHT11 error: {e}")
        return None, None
    finally:
        _KQ_LOCK.release()

# ====================== Soil Humidity Sensor =======================
def sensor_init_tu():
    # Initialize soil humidity sensor
    # Configure GPIO pin as input mode
    global _TU_INITIALIZED
    if _TU_INITIALIZED:
        return True
    
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(SOIL_PIN, GPIO.IN)
        _TU_INITIALIZED = True
        scheduled_logger.info("[Sensor] Soil sensor init success")
        mqtt_logger.info("[Sensor] Soil sensor init success")
        return True
    except Exception as e:
        scheduled_logger.error(f"[Sensor] Soil sensor init error: {e}")
        mqtt_logger.error(f"[Sensor] Soil sensor init error: {e}")
        return False

def sensor_cleanup_tu():
    # Clean up soil humidity sensor resources
    # Release GPIO pin
    global _TU_INITIALIZED
    if not _TU_INITIALIZED:
        return
    
    try:
        GPIO.cleanup(SOIL_PIN)
    except Exception:
        pass
    _TU_INITIALIZED = False
    scheduled_logger.info("[Sensor] Soil sensor cleaned up")
    mqtt_logger.info("[Sensor] Soil sensor cleaned up")

def read_soil_sensor():
    # Read soil humidity sensor data
    # Use thread lock to protect reading process
    # return: "Wet", "Dry", or "Unknown"
    global _TU_INITIALIZED
    if not _TU_INITIALIZED:
        return "Unknown"

    # Try to acquire lock, non-blocking mode
    if not _TU_LOCK.acquire(blocking=False):
        return "Unknown"

    try:
        level = GPIO.input(SOIL_PIN)
        if level == SOIL_WET_LEVEL:
            return "Wet"
        else:
            return "Dry"
    except Exception as e:
        scheduled_logger.error(f"[Sensor] Soil sensor error: {e}")
        mqtt_logger.error(f"[Sensor] Soil sensor error: {e}")
        return "Unknown"
    finally:
        _TU_LOCK.release()

# ====================== Camera Function =======================
def take_photo():
    # Take photo and save to local directory
    # Decide whether to use timestamp for naming based on configuration
    # return: Local path of the photo, returns None on failure
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
        return local_path
    except subprocess.CalledProcessError as e:
        return None

# ====================== File Upload =======================
def upload_file(local_path):
    # Upload file to remote server via SFTP
    # param local_path: Local file path
    # return: Remote file path, returns None on failure
    if not local_path:
        return None

    try:
        transport = paramiko.Transport((SERVER_IP, 22))
        transport.connect(username=USERNAME, password=PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)
        remote_path = os.path.join(REMOTE_DIR, os.path.basename(local_path))
        sftp.put(local_path, remote_path)
        sftp.close()
        transport.close()
        return remote_path
    except Exception as e:
        return None

# ====================== Task Execution Function =======================
def execute_task(logger, task_name):
    # Execute sensor collection and upload task
    # Called by both scheduled tasks and MQTT response tasks
    # param logger: Logger instance (distinguish between scheduled tasks and MQTT tasks)
    # param task_name: Task name identifier
    # return: Collection result message
    logger.info(f"[{task_name}] Starting task...")
    
    # Take photo
    photo = take_photo()
    if photo:
        logger.info(f"[{task_name}] Photo saved: {photo}")
    else:
        logger.warning(f"[{task_name}] Photo capture failed")

    # Read temperature and humidity
    temp, humi = read_sensor()
    if temp is not None and humi is not None:
        logger.info(f"[{task_name}] Temp: {temp:.1f}C, Humi: {humi:.1f}%")
    else:
        logger.warning(f"[{task_name}] Sensor read failed or busy")

    # Read soil humidity
    soil = read_soil_sensor()
    logger.info(f"[{task_name}] Soil: {soil}")

    # Upload photo
    remote_path = upload_file(photo)
    if remote_path:
        logger.info(f"[{task_name}] Photo uploaded: {remote_path}")
    else:
        logger.warning(f"[{task_name}] Upload failed")

    # Build result message
    result_msg = f"Photo:{remote_path},Temp:{temp},Humi:{humi},Soil:{soil}"
    logger.info(f"[{task_name}] Task completed: {result_msg}")
    return result_msg

# ====================== Scheduled Task Thread =======================
def scheduled_task(client):
    # Scheduled task thread function
    # Execute sensor collection and upload every hour
    # param client: MQTT client instance for publishing messages
    scheduled_logger.info("[Scheduled] Task thread started")
    
    while True:
        try:
            # Execute task
            result_msg = execute_task(scheduled_logger, "SCHEDULED")
            
            # Publish MQTT message
            client.publish(MQTT_TOPIC_PUBLISH, result_msg)
            scheduled_logger.info(f"[Scheduled] MQTT message sent")
            
        except Exception as e:
            scheduled_logger.error(f"[Scheduled] Task error: {e}")

        # Sleep for 1 hour
        scheduled_logger.info("[Scheduled] Sleeping for 1 hour...")
        time.sleep(3600)

# ====================== MQTT Callback Function =======================
def on_message(client, userdata, msg):
    # MQTT message reception callback function
    # Receive remote commands and execute sensor operations
    # param client: MQTT client instance
    # param userdata: User data
    # param msg: Received message
    try:
        payload = msg.payload.decode("utf-8").strip()
        mqtt_logger.info(f"[MQTT] Command received: {payload}")
        
        # Execute task in a new thread to avoid blocking MQTT main loop
        threading.Thread(target=mqtt_task, args=(client,)).start()
        
    except Exception as e:
        mqtt_logger.error(f"[MQTT] Message processing error: {e}")

def mqtt_task(client):
    # MQTT response task
    # Execute sensor collection and return results via MQTT
    # param client: MQTT client instance
    try:
        # Execute task
        result_msg = execute_task(mqtt_logger, "MQTT")
        
        # Publish results to MQTT topics
        client.publish(MQTT_TOPIC_PUBLISH, result_msg)
        client.publish(MQTT_TOPIC_RESPONSE, "success")
        mqtt_logger.info("[MQTT] Response sent")
        
    except Exception as e:
        mqtt_logger.error(f"[MQTT] Task execution error: {e}")
        client.publish(MQTT_TOPIC_RESPONSE, "failed")

# ====================== Main Program Entry =======================
if __name__ == "__main__":
    scheduled_logger.info("=" * 60)
    scheduled_logger.info("[Main] Program starting...")
    mqtt_logger.info("=" * 60)
    mqtt_logger.info("[Main] Program starting...")
    
    # Initialize sensors
    if not sensor_init_kq():
        scheduled_logger.error("[Main] DHT11 initialization failed")
    if not sensor_init_tu():
        scheduled_logger.error("[Main] Soil sensor initialization failed")
    
    # Create MQTT client
    client = mqtt.Client()
    client.on_message = on_message
    
    try:
        # Connect to MQTT server
        client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        client.subscribe(MQTT_TOPIC_SUBSCRIBE)
        mqtt_logger.info(f"[Main] MQTT connected, subscribed to: {MQTT_TOPIC_SUBSCRIBE}")
        
        # Start scheduled task thread
        scheduler_thread = threading.Thread(target=scheduled_task, args=(client,))
        scheduler_thread.daemon = True  # Set as daemon thread, automatically ends when main program exits
        scheduler_thread.start()
        scheduled_logger.info("[Main] Scheduled task thread started")
        
        # Start MQTT main loop (blocking)
        mqtt_logger.info("[Main] Starting MQTT loop...")
        client.loop_forever()
        
    except KeyboardInterrupt:
        scheduled_logger.info("[Main] Program interrupted by user")
        mqtt_logger.info("[Main] Program interrupted by user")
    except Exception as e:
        scheduled_logger.error(f"[Main] Fatal error: {e}")
        mqtt_logger.error(f"[Main] Fatal error: {e}")
    finally:
        # Clean up resources
        scheduled_logger.info("[Main] Cleaning up resources...")
        mqtt_logger.info("[Main] Cleaning up resources...")
        sensor_cleanup_kq()
        sensor_cleanup_tu()
        scheduled_logger.info("[Main] Program terminated")
        mqtt_logger.info("[Main] Program terminated")