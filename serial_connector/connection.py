import serial

from env import config

IDENTIFIER_LENGTH = int(config["IDENTIFIER_LENGTH"])
MESSAGE_LENGTH = int(config["MESSAGE_LENGTH"])


class SerialConnection:
    def __init__(self, serial_port: str, baud_rate: int, timeout: int):
        self.con = serial.Serial(serial_port, baud_rate, timeout=timeout)

    def close(self):
        self.con.close()


class ArduinoConnection(SerialConnection):
    def send_message(self, identifier: int, message: int):
        identifier = self.convert_to_bytes(identifier, IDENTIFIER_LENGTH)
        message = self.convert_to_bytes(message, MESSAGE_LENGTH)
        self.con.write(identifier + message)

    @staticmethod
    def convert_to_bytes(message, length):
        message = str(message)
        return bytes(message.zfill(length), "ASCII")


class LidarConnection(SerialConnection):
    def read_data(self):
        while True:
            counter = (
                self.con.in_waiting
            )  # count the number of bytes of the serial port
            if counter > 8:
                bytes_serial = self.con.read(9)  # read 9 bytes
                self.con.reset_input_buffer()  # reset buffer

                if (
                    bytes_serial[0] == 0x59 and bytes_serial[1] == 0x59
                ):  # check first two bytes
                    distance = (
                        bytes_serial[2] + bytes_serial[3] * 256
                    )  # distance in next two bytes
                    strength = (
                        bytes_serial[4] + bytes_serial[5] * 256
                    )  # signal strength in next two bytes
                    temperature = (
                        bytes_serial[6] + bytes_serial[7] * 256
                    )  # temp in next two bytes
                    temperature = (temperature / 8.0) - 256.0  # temp scaling and offset
                    return distance, strength, temperature

    def get_distance(self):
        return self.read_data()[0]
