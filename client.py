import socket


class Message:
    @staticmethod
    def last(n):
        return f"LAST {n}\n".encode()

    @staticmethod
    def poll(n):
        return f"POLL {n}\n".encode()

    @staticmethod
    def skip(n):
        return f"SKIP {n}\n".encode()
    
    @staticmethod
    def send(msg):
        return f"SEND {msg}\n".encode()

    quit = b"QUIT\n"


class BufferedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buffer = b""

    def read_line(self):
        try:
            pos = self._buffer.index(b"\n")
            line = self._buffer[:pos]
            self._buffer = self._buffer[pos+1:]
            return line.decode()
        except ValueError:
            self._buffer += self.recv(8192)
            return self.read_line()
    
    def read_int_line(self):
        return int(self.read_line())


class NanocatClient:
    def __init__(self, address="127.0.0.1:44322", username="NanocatUser"):
        self._last_id = 0
        self.username = username
        self.messages = []
        host, port = address.split(":")
        port = int(port)
        self._connect(host, port)

    def _connect(self, host, port):
        self.socket = BufferedSocket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))
        self._fetch_last_messages()
    
    def _fetch_last_messages(self, n=50):
        self.socket.send(Message.last(n))
        count = self.socket.read_int_line()
        for _ in range(count):
            self.messages.append(self.socket.read_line())
        self._last_id = self.socket.read_int_line()

    def _poll(self):
        self.socket.send(Message.poll(self._last_id))
        count = self.socket.read_int_line()
        return count != 0

    def _fetch_new_messages(self):
        self.socket.send(Message.skip(self._last_id))
        count = self.socket.read_int_line()
        new_messages = []
        for _ in range(count):
            new_messages.append(self.socket.read_line())
        self.messages += new_messages
        self._last_id = self.socket.read_int_line()
        return new_messages
    
    def send_message(self, message):
        message = f"{self.username}: {message}"
        self.socket.send(Message.send(message))
        id = self.socket.read_int_line()
        if id == self._last_id + 1:
            self.messages.append(message)
            self._last_id = id
            return [message]
        else:
            return self._fetch_new_messages()

    def check_for_messages(self):
        if self._poll():
            return self._fetch_new_messages()
        return []

    def quit(self):
        try:
            self.socket.send(Message.quit)
        except ConnectionAbortedError:
            pass # Expected
