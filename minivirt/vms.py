import sys
import os
import logging
import subprocess
import json
import shutil
import random
from textwrap import dedent
from functools import cached_property

from daemon import DaemonContext

from .qmp import QMP
from . import utils

ALPINE_ISO_URL = (
    'https://dl-cdn.alpinelinux.org/alpine/v3.15/releases/aarch64/'
    'alpine-standard-3.15.4-aarch64.iso'
)

FIRMWARE = '/opt/homebrew/share/qemu/edk2-aarch64-code.fd'

logger = logging.getLogger(__name__)


class VM:
    @classmethod
    def create(cls, db, name, image, disk):
        vm = cls(db, name)
        vm.vm_path.mkdir(parents=True)

        config = dict(
            image=image,
            disk=disk,
        )

        with vm.config_path.open('w') as f:
            json.dump(config, f, indent=2)

        if disk:
            subprocess.check_call(
                ['qemu-img', 'create', '-f', 'qcow2', vm.disk_path, disk]
            )

        return vm

    @classmethod
    def open(cls, db, name):
        return cls(db, name)

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.vm_path = db.vm_path(name)
        self.config_path = self.vm_path / 'config.json'
        self.qmp_path = self.vm_path / 'qmp'
        self.serial_path = self.vm_path / 'serial'
        self.ssh_config_path = self.vm_path / 'ssh-config'
        self.disk_path = self.vm_path / 'disk.qemu'

    @cached_property
    def config(self):
        with self.config_path.open() as f:
            return json.load(f)

    def connect_qmp(self):
        return QMP(self.qmp_path)

    def start(
        self,
        daemon=False,
        display=False,
        snapshot=False,
        wait_for_ssh=False,
    ):
        logger.info('Starting %s ...', self.name)

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

        qemu_cmd = [
            'qemu-system-aarch64',
            '-qmp', f'unix:{self.qmp_path},server,nowait',
            '-M', 'virt,highmem=off,accel=hvf',
            '-cpu', 'host',
            '-m', '4096',
            '-drive', (
                f'if=pflash,format=raw,file={FIRMWARE},readonly=on'
            ),
            '-boot', 'menu=on,splash-time=0',
            '-netdev', f'user,id=user,hostfwd=tcp::{ssh_port}-:22',
            '-device', 'virtio-net-pci,netdev=user,romfile=',
        ]

        if display:
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

        if self.config['disk']:
            qemu_cmd += [
                '-drive', f'if=virtio,file={self.disk_path}',
            ]

        qemu_cmd += [
            '-cdrom', self.db.image_path(self.config['image']),
        ]

        if snapshot:
            qemu_cmd += [
                '-snapshot',
            ]

        if daemon:
            qemu_cmd += [
                '-serial', f'unix:{self.serial_path},server=on,wait=off',
            ]

            if wait_for_ssh:
                if os.fork():
                    return utils.wait_for_ssh(ssh_port)

            with DaemonContext(
                files_preserve=[sys.stderr], stderr=sys.stderr
            ):
                subprocess.check_call(qemu_cmd)

        else:
            qemu_cmd += [
                '-serial', 'mon:stdio',
            ]
            subprocess.check_call(qemu_cmd)

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
