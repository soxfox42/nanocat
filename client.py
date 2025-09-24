import queue
import socket
import threading
import time


DEFAULT_ADDRESS = "127.0.0.1:44322"
POLL_TIME_MS = 5000


class Message:
    @staticmethod
    def poll(n):
        return f"POLL {n}\n".encode()

    @staticmethod
    def skip(n):
        return f"SKIP {n}\n".encode()

    @staticmethod
    def send(msg):
        return f"SEND {msg}\n".encode()

    hist = b"HIST\n"
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

        self._last_id = 0
        self._message_log = []
        self._load_message_log(address)

        self._send_thread.start()
        self._receive_thread.start()

    def _load_message_log(self, address):
        self._log_filename = address.replace(":", "_") + ".chat"
        try:
            with open(self._log_filename) as f:
                self._message_log = [l[:-1] for l in f]
            self._last_id = int(self._message_log.pop())
            self._fetch_new_messages()
        except OSError:
            # No log, let's fetch the full history
            self._fetch_all_messages()
        self.initial_messages = self._message_log[:]
        with self._receive_queue.mutex:
            self._receive_queue.queue.clear()

    def _save_message_log(self):
        with open(self._log_filename, "w") as f:
            for message in self._message_log:
                f.write(message + "\n")
            f.write(str(self._last_id) + "\n")
    
    def _connect(self, host, port):
        self.socket = BufferedSocket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))

    def _run_receive_thread(self):
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

    def _fetch_all_messages(self):
        self.socket.send(Message.hist)
        count = self.socket.read_int_line()
        for _ in range(count):
            message = self.socket.read_line()
            self._receive_queue.put(message)
            self._message_log.append(message)
        self._last_id = self.socket.read_int_line()

    def _fetch_new_messages(self):
        self.socket.send(Message.skip(self._last_id))
        count = self.socket.read_int_line()
        for _ in range(count):
            message = self.socket.read_line()
            self._receive_queue.put(message)
            self._message_log.append(message)
        self._last_id = self.socket.read_int_line()

    def _send_message(self, message):
        self.socket.send(Message.send(message))
        id = self.socket.read_int_line()
        if id == self._last_id + 1:
            self._receive_queue.put(message)
            self._message_log.append(message)
            self._last_id = id
        else:
            self._fetch_new_messages()

    def send_message(self, message):
        message = f"{self.username}: {message}"
        self._send_queue.put(message)
    
    def send_action(self, action):
        message = f"{self.username} {action}"
        self._send_queue.put(message)

    def send_motd(self, action):
        message = f"MOTD {action}"
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
        self._save_message_log()
        try:
            self.socket.send(Message.quit)
        except ConnectionAbortedError:
            pass  # Expected
