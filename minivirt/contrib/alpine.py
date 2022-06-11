import json
import logging
import re
import socket
import subprocess
from pathlib import Path

import click

from minivirt.utils import waitfor, WaitTimeout
from minivirt.vms import VM

ALPINE_ISO_URL = (
    'https://dl-cdn.alpinelinux.org/alpine/v{minor}/releases/aarch64/'
    'alpine-virt-{version}-aarch64.iso'
)

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

    def wait_for_pattern(self, pattern, limit=1000, timeout=10):
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
            self.wait(shell_prompt, timeout=30)

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

            self.send(b'echo "GRUB_TIMEOUT=0" >> /etc/default/grub\n')
            self.wait(shell_prompt)

            self.send(b'grub-mkconfig -o /boot/grub/grub.cfg\n')
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
def download(version):
    from minivirt.cli import db

    minor = re.match(r'\d+\.\d+', version).group()
    iso_url = ALPINE_ISO_URL.format(version=version, minor=minor)
    image_path = db.image_path(f'alpine-{version}-iso')
    assert not image_path.exists()
    image_path.mkdir(parents=True)

    filename = Path(iso_url).name
    logger.info('Downloading %s ...', filename)
    iso_path = image_path / filename
    subprocess.check_call(['curl', '-L', iso_url, '-o', iso_path])

    config = {
        'iso': filename,
    }
    config_path = image_path / 'config.json'
    with config_path.open('w') as f:
        json.dump(config, f, indent=2)


@cli.command()
@click.argument('name')
@click.option('--display', is_flag=True)
def bootstrap(name, display):
    from minivirt.cli import db

    vm = VM.open(db, name)
    Bootstrap(vm).bootstrap(display)
