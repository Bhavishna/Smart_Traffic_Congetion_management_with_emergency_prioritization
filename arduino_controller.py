import serial
import time
import serial.tools.list_ports

class ArduinoController:
    def __init__(self, port=None, baud_rate=9600):
        self.port = port
        self.baud_rate = baud_rate
        self.connection = None
        self.connected = False

    def auto_detect_port(self):
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if "Arduino" in p.description or "CH340" in p.description or "USB" in p.description:
                return p.device
        if ports:
            return ports[0].device
        return None

    def connect(self):
        try:
            if not self.port:
                self.port = self.auto_detect_port()
            if not self.port:
                print("No Arduino found. Running in simulation mode.")
                return False
            self.connection = serial.Serial(self.port, self.baud_rate, timeout=2)
            time.sleep(2)
            self.connected = True
            print(f"Connected to Arduino on {self.port}")
            return True
        except Exception as e:
            print(f"Arduino connection failed: {e}. Running in simulation mode.")
            self.connected = False
            return False

    def send_command(self, lane, color):
        cmd = f"{lane}{color}\n"
        if self.connected and self.connection:
            try:
                self.connection.write(cmd.encode())
                time.sleep(0.05)
            except Exception as e:
                print(f"Serial write error: {e}")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connected = False