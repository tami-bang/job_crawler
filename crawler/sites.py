# crawler/sites.py
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/sites.json")

def load_sites():
    """sites.json 로드"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
