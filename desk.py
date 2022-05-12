import logging
import sys
from logging import info, warning
from signal import signal, SIGINT
from time import sleep

from more_itertools import all_equal
from unsync import unsync

from env import config
from mqtt_connector.connection import MQTTConnection
from serial_connector.connection import ArduinoConnection, LidarConnection

POLLING_RATE = 1 / float(config["POLLING_RATE"])

UP = 1
DOWN = -1


class DeskLeg:
    def __init__(
        self,
        identifier: int,
        height: int,
        arduino_connection: ArduinoConnection,
        lidar_connection: LidarConnection,
    ):
        self.identifier = identifier
        self.height = height
        self.arduino_connection = arduino_connection
        self.lidar_connection = lidar_connection

    def check_direction(self):
        if self.height <= self.read_sensor():
            return DOWN
        else:
            return UP

    def set_height(self, height: int):
        self.height = height

    @unsync
    def move_legs(self):
        direction = self.check_direction()
        self.start_leg(direction)
        while self.read_sensor() * direction < self.height * direction:
            sleep(POLLING_RATE)
        self.stop_leg()
        return f"Leg ({self.identifier}) set to {self.height}. Sensor reading: {self.read_sensor()}"

    def start_leg(self, direction):
        self.arduino_connection.send_message(self.identifier, direction)

    def stop_leg(self):
        self.arduino_connection.send_message(self.identifier, 0)

    def read_sensor(self) -> float:
        return self.lidar_connection.get_distance()


class Desk:
    def __init__(self):
        self.arduino_connection = ArduinoConnection(
            config["ARDUINO_SERIAL_PORT"],
            int(config["ARDUINO_BAUD_RATE"]),
            int(config["ARDUINO_TIMEOUT"]),
        )
        identifiers = [int(config["RIGHT_LEG_IDENTIFIER"]), int(config["LEFT_LEG_IDENTIFIER"])]
        self.lidar_sensors = [
            LidarConnection(
                config["RIGHT_LIDAR_SENSOR_SERIAL_PORT"],
                int(config["LIDAR_SENSOR_BAUD_RATE"]),
                int(config["LIDAR_TIMEOUT"]),
            ),
            LidarConnection(
                config["LEFT_LIDAR_SENSOR_SERIAL_PORT"],
                int(config["LIDAR_SENSOR_BAUD_RATE"]),
                int(config["LIDAR_TIMEOUT"]),
            ),
        ]
        self.mqtt_connection = MQTTConnection(self.on_message)
        self.overall_height = 0
        self.desk_motors = [
            DeskLeg(identifier, self.overall_height, self.arduino_connection, lidar_connection)
            for identifier, lidar_connection in zip(identifiers, self.lidar_sensors)
        ]

    def on_message(self, client, userdata, msg):
        message = msg.payload.decode("ASCII")
        logging.info(f"MQTT message: {message}")
        if message == "up":
            self.max(UP)
        elif message == "down":
            self.max(DOWN)
        elif message.isnumeric():
            self.set_leg_heights(int(message))
        else:
            logging.warning(f"Invalid MQTT message {message}")

    def set_leg_heights(self, height: int):
        if height == self.overall_height:
            info("Height not changed")
            return

        self.overall_height = height

        directions = []
        for leg in self.desk_motors:
            leg.set_height(self.overall_height)
            directions.append(leg.check_direction())

        if not all_equal(directions):
            warning("Directions of Desk legs were different, resetting.")
            self.max(DOWN)
        else:
            tasks = [leg.move_legs() for leg in self.desk_motors]
            for task in tasks:
                print(task.result())

    def max(self, direction):
        for leg in self.desk_motors:
            leg.start_leg(direction)
        sleep(120)
        for leg in self.desk_motors:
            leg.stop_leg()

    def _sigint_handler(self, signal_received, frame):
        info("Shutting down desk service")
        self.__exit__(None, None, None)
        sys.exit(0)

    def __enter__(self):
        info("Starting desk service")
        signal(SIGINT, self._sigint_handler)
        self.mqtt_connection.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.arduino_connection.close()
        [lidar.close() for lidar in self.lidar_sensors]
        self.mqtt_connection.close()
