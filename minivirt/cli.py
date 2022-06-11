import logging
import os
import subprocess
from pathlib import Path

import click

from . import qemu
from .contrib import alpine
from .db import DB
from .vms import VM

logger = logging.getLogger(__name__)

_db_path = os.environ.get(
    'MINIVIRT_DB_PATH', Path.home() / '.cache' / 'minivirt'
)
db = DB(Path(_db_path))


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
    qemu.doctor()

    assert subprocess.check_output(
        ['socat', '-h']
    ).startswith(b'socat by Gerhard Rieger and contributors')

    assert b'minivirt/cli.py' in subprocess.check_output(['du', __file__])

    print('🚑👌')


@cli.command()
@click.argument('image')
@click.argument('name')
@click.option('--disk', default=None)
def create(image, name, **kwargs):
    VM.create(db, name, db.get_image(image), **kwargs)


@cli.command()
@click.argument('name')
@click.option('--daemon', is_flag=True)
@click.option('--display', is_flag=True)
@click.option('--snapshot', is_flag=True)
@click.option('--wait-for-ssh', type=int, default=None)
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
    for image_path in db.path.glob('images/*'):
        subprocess.check_call(
            ['du', '-sh', f'images/{image_path.name}'], cwd=db.path
        )
    for vm_path in db.path.glob('vms/*'):
        subprocess.check_call(
            ['du', '-sh', f'vms/{vm_path.name}'], cwd=db.path
        )


@cli.command()
@click.argument('name')
@click.argument('image')
def commit(name, image):
    vm = VM.open(db, name)
    vm.commit(image)


@cli.command()
@click.argument('image')
def save(image):
    db.save(image)


@cli.command()
@click.argument('image')
def load(image):
    db.load(image)


cli.add_command(alpine.cli, name='alpine')
