import json
import logging
import socket
import subprocess

from .utils import waitfor

logger = logging.getLogger(__name__)

QEMU_BINARY = 'qemu-system-aarch64'


def doctor():
    assert subprocess.check_output(
        ['qemu-system-aarch64', '--version']
    ).startswith(b'QEMU emulator version')

    assert subprocess.check_output(
        ['qemu-img', '--version']
    ).startswith(b'qemu-img version')


class QMP:
    def __init__(self, path):
        logger.debug('Waiting for QMP socket to show up ...')
        waitfor(path.exists)
        logger.debug('Connecting to QMP socket ...')
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(str(path))
        self.reader = self.sock.makefile(encoding='utf8')
        logger.debug('Connection to QMP estabilished.')
        self.initial_message = self.recv()
        self.send({'execute': 'qmp_capabilities'})
        assert 'return' in self.recv()
        logger.debug('Talking to QEMU %r', self.initial_message)

    def send(self, msg):
        logger.debug('Sending QMP message: %s.', msg)
        return self.sock.sendall(json.dumps(msg).encode('utf8'))

    def recv(self, bufsize=65536):
        msg = json.loads(self.reader.readline())
        logger.debug('Received QMP message: %s.', msg)
        return msg

    def quit(self):
        self.send({'execute': 'quit'})