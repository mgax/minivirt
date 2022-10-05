import fcntl
import json
import logging
import socket
import subprocess

from .utils import waitfor

logger = logging.getLogger(__name__)

machine = subprocess.check_output(['uname', '-m']).decode('utf8').strip()

if machine in ['arm64', 'aarch64']:
    arch = 'aarch64'
    binary = 'qemu-system-aarch64'
    command_prefix = [
        binary,
        '-cpu', 'host',
        '-machine', 'virt',
    ]

elif machine == 'x86_64':
    arch = 'x86_64'
    binary = 'qemu-system-x86_64'
    command_prefix = [
        binary,
        '-cpu', 'host',
    ]

else:
    raise RuntimeError(f'Unknown machine {machine!r}')


kernel = subprocess.check_output(['uname']).decode('utf8').strip()

if kernel == 'Darwin':
    os_name = 'macos'
    genisoimage_cmd = 'mkisofs'
    command_prefix += [
        '-accel', 'hvf',
    ]
    if machine == 'arm64':
        firmware = '/opt/homebrew/share/qemu/edk2-aarch64-code.fd'
        command_prefix += [
            '-drive', f'if=pflash,format=raw,file={firmware},readonly=on',
        ]

elif kernel == 'Linux':
    os_name = 'linux'
    command_prefix += [
        '-accel', 'kvm',
    ]
    genisoimage_cmd = 'genisoimage'
    if machine == 'aarch64':
        command_prefix += [
            '-bios', '/usr/share/qemu-efi-aarch64/QEMU_EFI.fd',
        ]

else:
    raise RuntimeError(f'Unknown kernel {kernel!r}')


def get_display_args():
    out = subprocess.check_output([binary, '-display', 'help']).decode('utf8')
    types = out.splitlines()[1:]

    for display_type in ['cocoa', 'gtk', 'sdl']:
        if display_type in types:
            display_argument = f'{display_type},show-cursor=on'
            break
    else:
        display_argument = 'default'

    return [
        '-device', 'virtio-gpu-pci',
        '-display', display_argument,
        '-device', 'qemu-xhci',
        '-device', 'usb-kbd',
        '-device', 'usb-tablet',
    ]


def doctor():
    assert subprocess.check_output(
        [command_prefix[0], '--version']
    ).startswith(b'QEMU emulator version')

    assert subprocess.check_output(
        ['qemu-img', '--version']
    ).startswith(b'qemu-img version')

    if os_name == 'linux':
        KVM_GET_API_VERSION = 0xae00
        KVM_API_VERSION = 12
        with open('/dev/kvm') as kvm:
            assert fcntl.ioctl(kvm, KVM_GET_API_VERSION) == KVM_API_VERSION


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

    def poweroff(self):
        self.send({'execute': 'system_powerdown'})
