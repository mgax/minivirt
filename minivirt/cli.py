import subprocess
import logging

import click

from .db import DB
from .vms import VM

logger = logging.getLogger(__name__)

db = DB()


@click.group()
@click.option('-v', '--verbose', is_flag=True)
@click.option('-d', '--debug', is_flag=True)
def cli(verbose, debug):
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(level=level)


@cli.command()
def doctor():
    assert subprocess.check_output(
        ['qemu-system-aarch64', '--version']
    ).startswith(b'QEMU emulator version')

    assert subprocess.check_output(
        ['qemu-img', '--version']
    ).startswith(b'qemu-img version')

    assert subprocess.check_output(
        ['socat', '-h']
    ).startswith(b'socat by Gerhard Rieger and contributors')

    assert b'minivirt/cli.py' in subprocess.check_output(['du', __file__])

    print('🚑👌')


@cli.command()
def download_alpine():
    db.download_alpine()


@cli.command()
@click.argument('image')
@click.argument('name')
@click.option('--disk', default=None)
def create(image, name, **kwargs):
    VM.create(db, name, image, **kwargs)


@cli.command()
@click.argument('name')
@click.option('--daemon', is_flag=True)
@click.option('--display', is_flag=True)
@click.option('--snapshot', is_flag=True)
@click.option('--wait-for-ssh', is_flag=True)
def start(name, **kwargs):
    vm = VM.open(db, name)
    vm.start(**kwargs)


@cli.command()
@click.argument('name')
def kill(name):
    vm = VM.open(db, name)
    vm.kill()


@cli.command()
@click.argument('name')
def destroy(name):
    vm = VM.open(db, name)
    vm.destroy()


@cli.command()
@click.argument('name')
def console(name):
    vm = VM.open(db, name)
    vm.console()


@cli.command()
def ls():
    subprocess.check_call(
        ['du', '-sh', *(p.name for p in db.path.glob('*'))],
        cwd=db.path
    )
