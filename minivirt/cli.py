import subprocess
import logging
from pathlib import Path

import click

from .db import DB
from .vms import ALPINE_ISO_URL, VM

logger = logging.getLogger(__name__)

db = DB()


@click.group()
@click.option('-v', '--verbose', is_flag=True)
def cli(verbose):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)


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
@click.option('--disk', default=None)
def create(name, **kwargs):
    image = Path(ALPINE_ISO_URL).name
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
def console(name):
    vm = VM.open(db, name)
    vm.console()


@cli.command()
def ls():
    subprocess.check_call(
        ['du', '-sh', *(p.name for p in db.path.glob('*'))],
        cwd=db.path
    )
