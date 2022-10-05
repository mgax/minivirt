import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from textwrap import dedent

from . import qemu, utils
from .configs import Config
from .exceptions import VmExists, VmIsRunning

VAGRANT_PRIVATE_KEY_PATH = Path(__file__).parent / 'vagrant-private-key'

logger = logging.getLogger(__name__)

RESOURCE_TYPES = {}


def resource_type(name):
    def decorator(cls):
        RESOURCE_TYPES[name] = cls
        return cls

    return decorator


@resource_type('disk')
class Disk:
    def __init__(self, path):
        self.path = path
        self.qemu_args = ['-drive', f'if=virtio,file={self.path}']


@resource_type('cdrom')
class CDROM:
    def __init__(self, path):
        self.path = path
        self.qemu_args = ['-cdrom', self.path]


class VM:
    @classmethod
    def create(cls, db, name, memory, image=None, disk=None):
        vm = cls(db, name)
        if vm.path.exists():
            raise VmExists(name)
        vm.path.mkdir(parents=True)

        if disk:
            vm.create_disk(disk)

        if image and image.config.get('disk'):
            vm.create_disk_with_base(image.path / 'disk.qcow2')

        vm.config.update(
            image=image and image.name,
            memory=memory,
        )
        vm.config.save()

        return vm

    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.path = db.vm_path(name)
        self.config = Config(self.path / 'config.json')
        self.qmp_path = self.path / 'qmp'
        self.serial_path = self.path / 'serial'
        self.disk_path = self.path / 'disk.qcow2'
        self.ssh_config_path = self.path / 'ssh-config'

    def __repr__(self):
        return f'<VM {self.name!r}>'

    def create_disk(self, size):
        assert not self.disk_path.exists()
        subprocess.check_call(
            ['qemu-img', 'create', '-f', 'qcow2', self.disk_path, size]
        )
        self.config.update(disk=size)
        self.config.save()

    def create_disk_with_base(self, path):
        assert not self.disk_path.exists()
        subprocess.check_call(
            [
                'qemu-img', 'create', '-q',
                '-b', self.relative_path(path),
                '-F', 'qcow2',
                '-f', 'qcow2',
                self.disk_path,
            ]
        )
        self.config.update(disk=True)
        self.config.save()

    def attach_disk(self, filename):
        self.config.setdefault('resources', []).append(
            {'type': 'disk', 'filename': filename}
        )
        self.config.save()

    def attach_cdrom(self, filename):
        self.config.setdefault('resources', []).append(
            {'type': 'cdrom', 'filename': filename}
        )
        self.config.save()

    def relative_path(self, path):
        return Path(os.path.relpath(path, self.path))

    @cached_property
    def image(self):
        if self.config.get('image'):
            return self.db.get_image(self.config['image'])

    @property
    def resources(self):
        if self.config.get('disk'):
            yield Disk(self.disk_path)

        if self.image and self.image.iso_path:
            yield CDROM(self.db.image_path(self.image.iso_path))

        for resource in self.config.get('resources', []):
            if resource['type'] == 'disk':
                yield Disk(self.path / resource['filename'])

            elif resource['type'] == 'cdrom':
                yield CDROM(self.path / resource['filename'])

            else:
                raise RuntimeError('Unknown resource type')

    def connect_qmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock_path = Path(tmp) / 'sock'
            sock_path.symlink_to(self.qmp_path)
            return qemu.QMP(sock_path)

    @property
    def is_running(self):
        if self.qmp_path.exists():
            try:
                self.connect_qmp()
            except ConnectionRefusedError:
                logger.warning('QEMU is gone for %s', self)
            else:
                return True

        return False

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

        with (self.path / 'run.json').open('w') as f:
            json.dump({'ssh_port': ssh_port}, f)

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

        qmp_path = self.qmp_path.relative_to(self.path)

        qemu_cmd = [
            *qemu.command_prefix,
            '-qmp', f'unix:{qmp_path},server,nowait',
            '-m', str(self.config['memory']),
            '-boot', 'menu=on,splash-time=0',
            '-netdev', f'user,id=user,hostfwd=tcp:127.0.0.1:{ssh_port}-:22',
            '-device', 'virtio-net-pci,netdev=user,romfile=',
        ]

        if display:
            qemu_cmd += qemu.get_display_args()

        else:
            qemu_cmd += [
                '-nographic',
            ]

        for resource in self.resources:
            qemu_cmd += resource.qemu_args

        if snapshot:
            qemu_cmd += [
                '-snapshot',
            ]

        if daemon:
            serial_path = self.serial_path.relative_to(self.path)
            qemu_cmd += [
                '-serial', f'unix:{serial_path},server=on,wait=off',
            ]

            if os.fork():
                if wait_for_ssh:
                    utils.wait_for_ssh(ssh_port, wait_for_ssh)

                return

            os.chdir(self.path)
            os.execvp(qemu_cmd[0], qemu_cmd)

        else:
            qemu_cmd += [
                '-serial', 'mon:stdio',
            ]

            os.chdir(self.path)
            os.execvp(qemu_cmd[0], qemu_cmd)

    def wait(self, timeout=10):
        logger.info('Waiting for %s to exit ...', self)
        utils.waitfor(lambda: not self.qmp_path.exists(), timeout=timeout)
        logger.info('%s has stopped.', self)

    def wait_for_ssh(self, timeout=30):
        with (self.path / 'run.json').open() as f:
            ssh_port = json.load(f)['ssh_port']
        utils.wait_for_ssh(ssh_port, timeout)

    def stop(self, wait=10):
        qmp = self.connect_qmp()
        qmp.poweroff()
        try:
            self.wait(wait)
        except utils.WaitTimeout:
            self.kill(wait=True)

    def kill(self, wait=False):
        if self.is_running:
            logger.info('%s is running; killing via QMP ...', self)
            qmp = self.connect_qmp()
            qmp.quit()
            if wait:
                self.wait()

        self.cleanup()

    def cleanup(self):
        self.qmp_path.unlink(missing_ok=True)
        self.serial_path.unlink(missing_ok=True)
        self.ssh_config_path.unlink(missing_ok=True)

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

    def commit(self):
        logger.info('Comitting image for %s', self)
        with self.db.create_image() as creator:
            config = {
                'disk': True,
            }
            with (creator.path / 'config.json').open('w') as f:
                json.dump(config, f, indent=2)
            subprocess.check_call([
                'qemu-img', 'convert', '-O', 'qcow2',
                self.disk_path, creator.path / self.disk_path.name
            ])

        return creator.image

    @contextmanager
    def run(self, **kwargs):
        try:
            self.start(daemon=True, **kwargs)
            yield
        finally:
            self.kill(wait=True)

    def fsck(self):
        if self.config.get('image'):
            if not self.db.image_path(self.config['image']).is_dir():
                yield f'missing image {self.config.get("image")}'
