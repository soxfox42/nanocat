import queue
import socket
import threading
import time


class Message:
    @staticmethod
    def skip(n):
        return f"SKIP {n}\n".encode()

    @staticmethod
    def wait(n):
        return f"WAIT {n}\n".encode()

    @staticmethod
    def send(msg):
        return f"SEND {msg}\n".encode()

    stop = b"STOP\n"
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
            return line.decode(errors="replace")
        except ValueError:
            if retry == 0:
                return ""
            self._buffer += self.recv(8192)
            return self.read_line(retry=retry - 1)

    def read_int_line(self):
        try:
            return int(self.read_line())
        except ValueError:
            return 0


class NanocatWaitClient:
    def __init__(self, address, username):
        self.username = username

        self._send_queue = queue.Queue()
        self._lock = threading.Lock()
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
            with open(self._log_filename) as file:
                self._message_log = [line[:-1] for line in file]
            self._last_id = int(self._message_log.pop())
            self._fetch_new_messages()
        except OSError:
            # No log, let's fetch the full history
            self._fetch_all_messages()
        self.initial_messages = self._message_log[:]

    def _save_message_log(self):
        with open(self._log_filename, "w") as file:
            for message in self._message_log:
                file.write(message + "\n")
            file.write(str(self._last_id) + "\n")

    def _connect(self, host, port):
        self.socket = BufferedSocket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))

    def _run_receive_thread(self):
        while True:
            with self._lock:
                self._fetch_new_messages(wait=True)
            time.sleep(0.1)

    def _run_send_thread(self):
        while True:
            message = self._send_queue.get()
            if self._lock.locked():
                self._stop_waiting()
            with self._lock:
                self._send_message(message)

    def _fetch_all_messages(self):
        self.socket.sendall(Message.hist)
        count = self.socket.read_int_line()
        for _ in range(count):
            message = self.socket.read_line()
            if self._message_callback:
                self._message_callback(message)
            self._message_log.append(message)
        self._last_id = self.socket.read_int_line()

    def _fetch_new_messages(self, wait=False):
        if wait:
            self.socket.sendall(Message.wait(self._last_id))
        else:
            self.socket.sendall(Message.skip(self._last_id))
        count = self.socket.read_int_line()
        for _ in range(count):
            message = self.socket.read_line()
            if self._message_callback:
                self._message_callback(message)
            self._message_log.append(message)
        self._last_id = self.socket.read_int_line()

    def _send_message(self, message):
        self.socket.sendall(Message.send(message))
        id = self.socket.read_int_line()
        if id == self._last_id + 1:
            if self._message_callback:
                self._message_callback(message)
            self._message_log.append(message)
            self._last_id = id
        else:
            self._fetch_new_messages()

    def _stop_waiting(self):
        self.socket.sendall(Message.stop)

    def send_message(self, message):
        message = f"{self.username}: {message}"
        self._send_queue.put(message)

    def send_action(self, action):
        message = f"{self.username} {action}"
        self._send_queue.put(message)

    def send_motd(self, action):
        message = f"MOTD {action}"
        self._send_queue.put(message)

    def on_message_received(self, callback):
        self._message_callback = callback

    def quit(self):
        self._save_message_log()
        try:
            self.socket.sendall(Message.quit)
        except (ConnectionAbortedError, ConnectionResetError):
            pass  # Expected
