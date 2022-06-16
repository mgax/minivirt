import logging
import shlex
import subprocess

import click

from minivirt.vms import VM

logger = logging.getLogger(__name__)


def ssh(vm, command):
    logger.info('Running %r', command)
    subprocess.check_call(['ssh', f'{vm.name}.miv', command])


@click.group()
def cli():
    pass


@cli.command()
@click.argument('image')
@click.argument('name')
def build(image, name):
    from minivirt.cli import db

    sed_rule = r's|# \(http://dl-cdn.alpinelinux.org/alpine/.*/community\)|\1|'
    packages = [
        'py3-pip',
        'qemu',
        'qemu-system-x86_64',
        'qemu-img',
        'socat',
        'tar',
        'git',
    ]

    vm = VM.create(db, name, db.get_image(image), memory=1024)
    with vm.run(wait_for_ssh=30):
        ssh(vm, f'sed -i {shlex.quote(sed_rule)} /etc/apk/repositories')
        ssh(vm, f'apk add {" ".join(packages)}')
        ssh(vm, 'poweroff')
        vm.wait()


@cli.command()
@click.argument('name')
def testsuite(name):
    from minivirt.cli import db

    vm = VM.open(db, name)
    with vm.run(wait_for_ssh=30, snapshot=True):
        ssh(vm, 'git clone https://github.com/mgax/minivirt')
        ssh(vm, 'pip3 install ./minivirt')
        ssh(vm, 'pip3 install pytest')
        ssh(vm, 'miv doctor')
        ssh(vm, 'cd minivirt; pytest -vv')
