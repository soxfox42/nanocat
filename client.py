import queue
import socket
import threading
import time


DEFAULT_ADDRESS = "127.0.0.1:44322"
POLL_TIME_MS = 5000


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

    def read_line(self, retry=10):
        try:
            pos = self._buffer.index(b"\n")
            line = self._buffer[:pos]
            self._buffer = self._buffer[pos + 1 :]
            return line.decode()
        except ValueError:
            if retry == 0:
                raise
            self._buffer += self.recv(8192)
            return self.read_line(retry=retry - 1)

    def read_int_line(self):
        return int(self.read_line())


class NanocatClient:
    def __init__(self, address=DEFAULT_ADDRESS, username="NanocatUser"):
        self._last_id = 0
        self.username = username

        self._send_queue = queue.Queue()
        self._receive_queue = queue.Queue()
        self._lock = threading.RLock()
        self._send_thread = threading.Thread(target=self._run_send_thread, daemon=True)
        self._receive_thread = threading.Thread(
            target=self._run_receive_thread, daemon=True
        )

        host, port = address.split(":")
        port = int(port)
        self._connect(host, port)

        self._send_thread.start()
        self._receive_thread.start()

    def _connect(self, host, port):
        self.socket = BufferedSocket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))

    def _run_receive_thread(self):
        self._fetch_last_messages()
        while True:
            with self._lock:
                if self._poll():
                    self._fetch_new_messages()
            time.sleep(POLL_TIME_MS / 1000)

    def _run_send_thread(self):
        while True:
            message = self._send_queue.get()
            with self._lock:
                self._send_message(message)

    def _poll(self):
        self.socket.send(Message.poll(self._last_id))
        count = self.socket.read_int_line()
        return count != 0

    def _fetch_last_messages(self, n=50):
        self.socket.send(Message.last(n))
        count = self.socket.read_int_line()
        for _ in range(count):
            self._receive_queue.put(self.socket.read_line())
        self._last_id = self.socket.read_int_line()

    def _fetch_new_messages(self):
        self.socket.send(Message.skip(self._last_id))
        count = self.socket.read_int_line()
        for _ in range(count):
            self._receive_queue.put(self.socket.read_line())
        self._last_id = self.socket.read_int_line()

    def _send_message(self, message):
        message = f"{self.username}: {message}"
        self.socket.send(Message.send(message))
        id = self.socket.read_int_line()
        if id == self._last_id + 1:
            self._receive_queue.put(message)
            self._last_id = id
            return [message]
        else:
            return self._fetch_new_messages()

    def send_message(self, message):
        self._send_queue.put(message)

    def receive_messages(self):
        messages = []
        while True:
            try:
                messages.append(self._receive_queue.get(block=False))
            except queue.Empty:
                break
        return messages

    def quit(self):
        try:
            self.socket.send(Message.quit)
        except ConnectionAbortedError:
            pass  # Expected
