import logging
import sys

def logger(name = __name__):
    
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        log_format = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        
        logger.addHandler(console_handler)
        
        return logger
