import logging
import os
from datetime import datetime

def setup_logger(name: str, log_file: str = "maktaba.log", level=logging.INFO):
    """Function to setup as many loggers as you want."""
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", log_file)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers if logger is already initialized
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# Global default logger
logger = setup_logger("Maktaba-OS")
