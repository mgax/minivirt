import json
import logging
import os
import random
import shutil
import subprocess
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from textwrap import dedent

from . import qemu, utils
from .exceptions import VmIsRunning

VAGRANT_PRIVATE_KEY_PATH = Path(__file__).parent / 'vagrant-private-key'

logger = logging.getLogger(__name__)


class VM:
    @classmethod
    def create(cls, db, name, image, memory, disk=None):
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
                    '-b', vm.relative_path(image.path / 'disk.qcow2'),
                    '-F', 'qcow2',
                    '-f', 'qcow2',
                    vm.disk_path,
                ]
            )

        vm._write_config(
            dict(
                image=image.name,
                disk=disk,
                memory=memory,
            )
        )

        return vm

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.path = db.vm_path(name)
        self.config_path = self.path / 'config.json'
        self.qmp_path = self.path / 'qmp'
        self.serial_path = self.path / 'serial'
        self.disk_path = self.path / 'disk.qcow2'
        self.ssh_config_path = self.path / 'ssh-config'

    def relative_path(self, path):
        return Path(os.path.relpath(path, self.path))

    def __repr__(self):
        return f'<VM {self.name!r}>'

    def _write_config(self, config):
        with self.config_path.open('w') as f:
            json.dump(config, f, indent=2)

        self.__dict__.pop('config', None)

    @cached_property
    def config(self):
        with self.config_path.open() as f:
            return json.load(f)

    @cached_property
    def image(self):
        return self.db.get_image(self.config['image'])

    def connect_qmp(self):
        return qemu.QMP(self.qmp_path)

    @property
    def is_running(self):
        return self.qmp_path.exists()

    def start(
        self,
        daemon=False,
        display=False,
        snapshot=False,
        wait_for_ssh=False,
    ):
        if self.is_running:
            raise VmIsRunning(f'{self} is already running')

        logger.info('Starting %s ...', self.name)

        ssh_port = random.randrange(20000, 32000)

        ssh_private_key_path = self.path / 'ssh-private-key'
        shutil.copy(VAGRANT_PRIVATE_KEY_PATH, ssh_private_key_path)
        ssh_private_key_path.chmod(0o600)

        with self.ssh_config_path.open('w') as f:
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

        self.ssh_config_path.chmod(0o644)

        qemu_cmd = [
            *qemu.command_prefix,
            '-qmp', f'unix:{self.qmp_path},server,nowait',
            '-m', str(self.config['memory']),
            '-boot', 'menu=on,splash-time=0',
            '-netdev', f'user,id=user,hostfwd=tcp:127.0.0.1:{ssh_port}-:22',
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
                    utils.wait_for_ssh(ssh_port, wait_for_ssh)

                return

            os.execvp(qemu_cmd[0], qemu_cmd)

        else:
            qemu_cmd += [
                '-serial', 'mon:stdio',
            ]
            os.execvp(qemu_cmd[0], qemu_cmd)

    def wait(self, timeout=10):
        logger.info('Waiting for %s to exit ...', self)
        utils.waitfor(lambda: not self.qmp_path.exists(), timeout=timeout)
        logger.info('%s has stopped.', self)

    def kill(self, wait=False):
        if self.qmp_path.exists():
            logger.info('%s is running; killing via QMP ...', self)
            qmp = self.connect_qmp()
            qmp.quit()
            if wait:
                self.wait()

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

    def ssh(self, *args, capture=False):
        fn = subprocess.check_output if capture else subprocess.check_call
        hostname = f'{self.name}.miv'
        return fn(['ssh', '-F', self.ssh_config_path, hostname, *args])

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

    def fsck(self):
        if not self.db.image_path(self.config['image']).is_dir():
            yield f'missing image {self.image}'
