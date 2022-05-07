import paho.mqtt.client as mqtt

from env import config


class MQTTConnection:
    def __init__(self, message_func):
        client = mqtt.Client()
        client.connect(config["MQTT_CLIENT"], int(config["MQTT_PORT"]))
        client.on_connect = self.on_connect
        client.on_message = message_func

        self.client = client

    @staticmethod
    def on_connect(client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        client.subscribe(config["TOPIC_NAME"])

    def start(self):
        self.client.loop_forever()

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()
