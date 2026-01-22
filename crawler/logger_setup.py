# crawler/logger_setup.py
import logging

def setup_logger(name="crawler"):
    # 로깅 기본 설정
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    handler = logging.FileHandler("crawler.log", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    
    if not logger.hasHandlers():
        logger.addHandler(handler)
    
    return logger
