import os
import logging
import subprocess
import json
import shutil
import random
from textwrap import dedent
from functools import cached_property
from pathlib import Path
from contextlib import contextmanager


from .qmp import QMP
from . import utils

FIRMWARE = '/opt/homebrew/share/qemu/edk2-aarch64-code.fd'

VAGRANT_PRIVATE_KEY_PATH = Path(__file__).parent / 'vagrant-private-key'

logger = logging.getLogger(__name__)


class VM:
    @classmethod
    def create(cls, db, name, image, disk=None):
        vm = cls(db, name)
        assert not vm.path.exists()
        vm.path.mkdir(parents=True)

        if disk:
            subprocess.check_call(
                ['qemu-img', 'create', '-f', 'qcow2', vm.disk_path, disk]
            )

        if image.config.get('disk'):
            disk = True
            subprocess.check_call(
                [
                    'qemu-img', 'create', '-q',
                    '-b', image.path / 'disk.qcow2',
                    '-F', 'qcow2',
                    '-f', 'qcow2',
                    vm.disk_path,
                ]
            )

        config = dict(
            image=image.name,
            disk=disk,
        )

        with vm.config_path.open('w') as f:
            json.dump(config, f, indent=2)

        return vm

    @classmethod
    def open(cls, db, name):
        return cls(db, name)

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.path = db.vm_path(name)
        self.config_path = self.path / 'config.json'
        self.qmp_path = self.path / 'qmp'
        self.serial_path = self.path / 'serial'
        self.disk_path = self.path / 'disk.qcow2'

    def __repr__(self):
        return f'<VM {self.name!r}>'

    @cached_property
    def config(self):
        with self.config_path.open() as f:
            return json.load(f)

    @cached_property
    def image(self):
        return self.db.get_image(self.config['image'])

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

        ssh_private_key_path = self.path / 'ssh-private-key'
        shutil.copy(VAGRANT_PRIVATE_KEY_PATH, ssh_private_key_path)
        ssh_private_key_path.chmod(0o600)

        ssh_config_path = self.path / 'ssh-config'
        with ssh_config_path.open('w') as f:
            f.write(
                dedent(
                    f'''\
                        Host {self.name}.miv
                            StrictHostKeyChecking no
                            UserKnownHostsFile /dev/null
                            Hostname localhost
                            Port {ssh_port}
                            User root
                            IdentityFile {ssh_private_key_path}
                    '''
                )
            )

        ssh_config_path.chmod(0o644)

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

        if self.image.iso_path:
            qemu_cmd += [
                '-cdrom', self.db.image_path(self.image.iso_path),
            ]

        if snapshot:
            qemu_cmd += [
                '-snapshot',
            ]

        if daemon:
            qemu_cmd += [
                '-serial', f'unix:{self.serial_path},server=on,wait=off',
            ]

            if os.fork():
                if wait_for_ssh:
                    utils.wait_for_ssh(ssh_port)

                return

            os.execvp(qemu_cmd[0], qemu_cmd)

        else:
            qemu_cmd += [
                '-serial', 'mon:stdio',
            ]
            os.execvp(qemu_cmd[0], qemu_cmd)

    def kill(self, wait=False):
        if self.qmp_path.exists():
            qmp = self.connect_qmp()
            qmp.quit()
            if wait:
                utils.waitfor(lambda: not self.qmp_path.exists())

    def destroy(self):
        self.kill(wait=True)
        if self.path.exists():
            shutil.rmtree(self.path)

    def console(self):
        os.execvp(
            'socat',
            [
                'socat',
                'stdin,raw,echo=0,escape=0x1d',
                f'unix-connect:{self.serial_path}',
            ],
        )

    def commit(self, image):
        image_path = self.db.image_path(image)
        image_path.mkdir(parents=True)
        config = {
            'disk': True,
        }
        with (image_path / 'config.json').open('w') as f:
            json.dump(config, f, indent=2)
        subprocess.check_call([
            'qemu-img', 'convert', '-O', 'qcow2',
            self.disk_path, image_path / self.disk_path.name
        ])

    @contextmanager
    def run(self, **kwargs):
        logger.info('Running %s ...', self.name)
        try:
            self.start(daemon=True, **kwargs)
            yield
        finally:
            self.kill(wait=True)
