import json
import logging
import re
import socket
import subprocess
from pathlib import Path

import click

from minivirt.qemu import arch
from minivirt.utils import waitfor, WaitTimeout
from minivirt.vms import VM

VAGRANT_PUBLIC_KEY_URL = (
    'https://raw.githubusercontent.com'
    '/hashicorp/vagrant/master/keys/vagrant.pub'
)

logger = logging.getLogger(__name__)


class Console:
    def __init__(self, path):
        logger.debug('Waiting for %s to show up ...', path)
        waitfor(path.exists)
        logger.debug('Connecting ...')
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        waitfor(lambda: self.sock.connect(str(path)) or True)
        self.sock.settimeout(1)
        logger.debug('Connection successful')

    def recv(self):
        chunk = self.sock.recv(10000)
        logger.debug('Received %r', chunk)
        return chunk

    def wait_for_pattern(self, pattern, limit=1000, timeout=30):
        buffer = b''

        def look_for_pattern():
            nonlocal buffer

            while not re.search(pattern, buffer, re.MULTILINE):
                try:
                    buffer += self.recv()
                    buffer = buffer[-limit:]
                except OSError:
                    return

            return True

        try:
            waitfor(look_for_pattern, timeout=timeout)
        except (OSError, WaitTimeout):
            logger.warning('Timeout waiting for %r; got %r', pattern, buffer)
            raise

        return buffer

    def send(self, message):
        logger.debug('Sending %r', message)
        self.sock.sendall(message)


class Bootstrap:
    def __init__(self, vm):
        self.vm = vm

    def wait(self, pattern, **kwargs):
        output = self.console.wait_for_pattern(pattern, **kwargs)
        logger.info('Received: %r', output)
        return output

    def send(self, message):
        logger.info('Sending: %r', message)
        self.console.send(message)

    def bootstrap(self, display=False):
        logger.info('Bootstrapping Alpine %s ...', self.vm)
        try:
            self.vm.start(daemon=True, display=display)
            self.console = Console(self.vm.serial_path)
            self.wait(b'\n\rlocalhost login: $')

            logger.info('VM is up, logging in ...')
            self.send(b'root\n')
            shell_prompt = b'\r\n(localhost|alpine):~# (\x1b\\[6n)?$'
            self.wait(shell_prompt)

            logger.info('Login successful, building image ...')
            self.send(b'hwclock --hctosys\n')
            self.wait(shell_prompt)

            self.send(b'setup-alpine -q\n')
            self.wait(
                b'\r\nSelect keyboard layout: \\[none\\] $'
            )
            self.send(b'\n')
            self.wait(shell_prompt)

            self.send(b'setup-disk -m sys -s 0 /dev/vda\n')
            self.wait(
                b'\r\nWARNING: Erase the above disk\\(s\\) '
                b'and continue\\? \\(y/n\\) \\[n\\] $'
            )
            self.send(b'y\n')
            self.wait(shell_prompt, timeout=60)

            logger.info('Rebooting from disk ...')
            self.send(b'reboot\n')
            self.wait(b'\n\ralpine login: $')

            logger.info('VM is back up, logging in ...')
            self.send(b'root\n')

            self.send(
                b'echo "http://dl-cdn.alpinelinux.org/alpine/v3.15/community" '
                b'>> /etc/apk/repositories\n'
            )
            self.wait(shell_prompt)

            self.send(b'setup-sshd\n')
            self.wait(
                b"\r\nWhich SSH server\\? "
                b"\\('openssh', 'dropbear' or 'none'\\) \\[openssh\\] "
            )
            self.send(b'\n')
            self.wait(shell_prompt)

            self.send(
                f'apk add curl '
                f'&& mkdir ~/.ssh '
                f'&& chmod 700 ~/.ssh '
                f'&& curl {VAGRANT_PUBLIC_KEY_URL} > ~/.ssh/authorized_keys '
                f'&& chmod 600 ~/.ssh/authorized_keys\n'
                .encode('utf8')
            )
            self.wait(shell_prompt)

            if arch == 'aarch64':
                self.send(b'echo "GRUB_TIMEOUT=0" >> /etc/default/grub\n')
                self.wait(shell_prompt)

                self.send(b'grub-mkconfig -o /boot/grub/grub.cfg\n')
                self.wait(shell_prompt)

            else:
                self.send(b'echo "DEFAULT virt" >> /boot/extlinux.conf\n')
                self.wait(shell_prompt)

            self.send(b'poweroff\n')
            waitfor(lambda: not self.vm.qmp_path.exists())

        finally:
            self.vm.kill()

        logger.info('Build finished.')


@click.group()
def cli():
    pass


@cli.command()
@click.argument('version')
@click.argument('name', default=None)
def download(version, name):
    from minivirt.cli import db

    minor = re.match(r'\d+\.\d+', version).group()
    iso_url = (
        f'https://dl-cdn.alpinelinux.org/alpine/v{minor}/releases/{arch}/'
        f'alpine-virt-{version}-{arch}.iso'
    )
    if name is None:
        name = f'alpine-{version}-{arch}-iso'

    with db.create_image() as creator:
        filename = Path(iso_url).name
        logger.info('Downloading %s ...', filename)
        iso_path = creator.path / filename
        subprocess.check_call(['curl', '-L', iso_url, '-o', iso_path])

        config = {
            'iso': filename,
        }
        config_path = creator.path / 'config.json'
        with config_path.open('w') as f:
            json.dump(config, f, indent=2)

    creator.image.tag(name)


@cli.command()
@click.argument('name')
@click.option('--display', is_flag=True)
def bootstrap(name, display):
    from minivirt.cli import db

    vm = db.get_vm(name)
    Bootstrap(vm).bootstrap(display)


@cli.command()
@click.argument('image')
@click.argument('name')
@click.argument('disk')
@click.option('--display', is_flag=True)
def install(image, name, disk, display):
    from minivirt.cli import db
    vm = VM.create(db, name, db.get_image(image), memory='512', disk=disk)
    Bootstrap(vm).bootstrap(display)
