import logging
import subprocess
from pathlib import Path
from time import time, sleep
import socket
import json
import shutil

import click
import daemon

ALPINE_ISO_URL = (
    'https://dl-cdn.alpinelinux.org/alpine/v3.16/releases/aarch64/'
    'alpine-standard-3.16.0-aarch64.iso'
)

FIRMWARE = '/opt/homebrew/share/qemu/edk2-aarch64-code.fd'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DB:
    def __init__(self):
        self.path = Path.home() / '.cache' / 'minivirt'
        self.path.mkdir(parents=True, exist_ok=True)

    def image_path(self, filename):
        return self.path / filename

    def vm_path(self, name):
        return self.path / name

    def download_image(self, url, filename):
        subprocess.check_call(
            ['curl', '-L', url, '-o', self.image_path(filename)]
        )


def waitfor(condition, timeout=10, poll_interval=0.1):
    expires = time() + timeout
    while time() < expires:
        logger.debug('Polling for %r ...', condition)
        rv = condition()
        if rv:
            logger.debug('Polling for %r successful: %r.', condition, rv)
            return rv
        sleep(poll_interval)

    raise RuntimeError('Timeout expired')


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


class VM:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.vm_path = db.vm_path(name)
        self.qmp_path = self.vm_path / 'qmp'

    def connect_qmp(self):
        return QMP(self.qmp_path)

    def start(self, image):
        logger.info('Starting %s ...', self.name)
        self.vm_path.mkdir(parents=True)
        try:
            subprocess.check_call(
                [
                    'qemu-system-aarch64',
                    '-qmp', f'unix:{self.qmp_path},server,nowait',
                    '-M', 'virt,highmem=off,accel=hvf',
                    '-cpu', 'cortex-a72',
                    '-smp', '4',
                    '-m', '4096',
                    '-drive', (
                        f'if=pflash,format=raw,file={FIRMWARE},readonly=on'
                    ),
                    '-boot', 'menu=on,splash-time=0',
                    '-device', 'virtio-gpu-pci',
                    '-display', 'default,show-cursor=on',
                    '-device', 'qemu-xhci',
                    '-device', 'usb-kbd',
                    '-device', 'usb-tablet',
                    '-cdrom', db.image_path(image),
                ]
            )

        finally:
            self.cleanup()

    def kill(self):
        if self.qmp_path.exists():
            qmp = self.connect_qmp()
            qmp.quit()

        self.cleanup()

    def cleanup(self):
        if self.vm_path.exists():
            shutil.rmtree(self.vm_path)


db = DB()


@click.group()
def cli():
    pass


@cli.command()
def doctor():
    qemu_version = subprocess.check_output(
        ['qemu-system-aarch64', '--version']
    )
    assert qemu_version.startswith(b'QEMU emulator version')
    logger.info('🚑👌')


@cli.command()
def download_alpine():
    image = Path(ALPINE_ISO_URL).name
    logger.info('Downloading %s ...', image)
    db.download_image(ALPINE_ISO_URL, image)


@cli.command()
@click.argument('name')
def start(name):
    image = Path(ALPINE_ISO_URL).name
    vm = VM(db, name)
    import sys
    with daemon.DaemonContext(files_preserve=[sys.stderr], stderr=sys.stderr):
        print('foo', file=sys.stderr, flush=True)
        vm.start(image)


@cli.command()
@click.argument('name')
def kill(name):
    vm = VM(db, name)
    vm.kill()


logging.basicConfig()
cli()
