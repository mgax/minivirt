import re
import shutil
import socket
import sys
import threading

from . import utils


class StatusLine:
    def __init__(self, vm):
        self.vm = vm
        self.prev = None

    def serial_lines(self):
        utils.waitfor(self.vm.serial_path.exists)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(self.vm.serial_path))
        reader = sock.makefile('rb')
        for raw_line in reader:
            line = re.sub(b'\x1b\\[\\d+m', b'', raw_line)
            line = re.sub(rb'[^ -~]', b'', line).strip()
            if line:
                yield line.decode('latin1')

    def run(self):
        for line in self.serial_lines():
            if self.please_stop:
                return

            line = line[:shutil.get_terminal_size().columns]

            if self.prev:
                print(' ' * len(self.prev), end='\r')  # noqa: T201

            print(line, end='\r')  # noqa: T201
            self.prev = line

    def start(self):
        self.please_stop = False
        if sys.stdout.isatty():
            threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.please_stop = True
        if self.prev:
            print(' ' * len(self.prev), end='\r')  # noqa: T201
