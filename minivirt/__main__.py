import sys
import os
import logging
import subprocess
from pathlib import Path
from time import time, sleep
import socket
import json
import shutil
import random
from textwrap import dedent

import click
from daemon import DaemonContext

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
        self.serial_path = self.vm_path / 'serial'
        self.ssh_config_path = self.vm_path / 'ssh-config'

    def connect_qmp(self):
        return QMP(self.qmp_path)

    def start(self, image, display=False, daemon=False):
        logger.info('Starting %s ...', self.name)

        self.vm_path.mkdir(parents=True)
        ssh_port = random.randrange(20000, 32000)
        with self.ssh_config_path.open('w') as f:
            f.write(
                dedent(
                    f'''\
                        Host {self.name}.minivirt
                            StrictHostKeyChecking no
                            UserKnownHostsFile /dev/null
                            Hostname localhost
                            Port {ssh_port}
                            User root
                    '''
                )
            )

        self.ssh_config_path.chmod(0o644)

        try:
            qemu_cmd = [
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
                '-netdev', f'user,id=user,hostfwd=tcp::{ssh_port}-:22',
                '-device', 'virtio-net-pci,netdev=user,romfile=',
                '-cdrom', db.image_path(image),
            ]

            if display:
                assert not daemon, (
                    '--daemon and --display are mutually exclusive'
                )
                qemu_cmd += [
                    '-device', 'virtio-gpu-pci',
                    '-display', 'default,show-cursor=on',
                    '-device', 'qemu-xhci',
                    '-device', 'usb-kbd',
                    '-device', 'usb-tablet',
                ]

            else:
                qemu_cmd += [
                    '-nographic',
                ]

            if daemon:
                qemu_cmd += [
                    '-serial', f'unix:{self.serial_path},server=on,wait=off',
                ]
                with DaemonContext(
                    files_preserve=[sys.stderr], stderr=sys.stderr
                ):
                    subprocess.check_call(qemu_cmd)

            else:
                qemu_cmd += [
                    '-serial', 'mon:stdio',
                ]
                subprocess.check_call(qemu_cmd)

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

    def console(self):
        os.execvp(
            'socat',
            [
                'socat',
                'stdin,raw,echo=0,escape=0x1d',
                f'unix-connect:{self.serial_path}',
            ],
        )


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
@click.option('--display', default=False)
@click.option('--daemon', default=False)
def start(name, **kwargs):
    image = Path(ALPINE_ISO_URL).name
    vm = VM(db, name)
    vm.start(image, **kwargs)


@cli.command()
@click.argument('name')
def kill(name):
    vm = VM(db, name)
    vm.kill()


@cli.command()
@click.argument('name')
def console(name):
    vm = VM(db, name)
    vm.console()


logging.basicConfig()
cli()
