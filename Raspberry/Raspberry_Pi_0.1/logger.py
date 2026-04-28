import logging
from logging.handlers import RotatingFileHandler
import os

def get_logger(config):
    log_path = config["log_path"]
    max_bytes = config["max_bytes"]
    backup_count = config["backup_count"]
    log_format = config["format"]

    log_dir = os.path.dirname(log_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(log_format))

    logger = logging.getLogger(log_path)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    return logger