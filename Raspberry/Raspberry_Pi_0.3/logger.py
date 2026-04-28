import logging
from logging.handlers import RotatingFileHandler
import os

# Logger cache to avoid duplicate logger instances
_logger_cache = {}

def get_logger(config):
    # Get or create a logger instance based on log_path
    # param config: Logger configuration dictionary
    # return: Configured logger instance
    log_path = config['log_path']
    
    # Check if logger already exists in cache
    if log_path in _logger_cache:
        return _logger_cache[log_path]
    
    max_bytes = config['max_bytes']
    backup_count = config['backup_count']
    log_format = config['format']

    log_dir = os.path.dirname(log_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(log_format))

    logger = logging.getLogger(log_path)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    
    # Cache the logger instance
    _logger_cache[log_path] = logger

    return logger