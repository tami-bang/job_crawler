import os

from crawler.database import DEFAULT_DB_PATH, get_connection, init_database


def get_db_path():
    return os.getenv("JOB_RADAR_DB_PATH", DEFAULT_DB_PATH)


def initialize_api_database():
    init_database(get_db_path())


def open_database():
    return get_connection(get_db_path())
