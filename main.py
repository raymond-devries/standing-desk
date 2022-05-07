import logging

from desk import Desk

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    with Desk():
        logging.info("Desk service started")
