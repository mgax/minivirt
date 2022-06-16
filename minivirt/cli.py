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

    tar_output = subprocess.check_output(['tar', '--version'])
    assert any(impl in tar_output for impl in [b'GNU tar', b'bsdtar'])

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
@click.option('-a', '--all', 'all_', is_flag=True)
def ps(all_):
    for vm in db.iter_vms():
        is_running = vm.is_running
        if not is_running and not all_:
            continue
        du_output = subprocess.check_output(['du', '-sh', vm.path])
        size = du_output.decode('utf8').split()[0]
        up_or_down = 'up' if is_running else 'down'
        print(vm.name, up_or_down, size)


@cli.command()
def images():
    for image in db.iter_images():
        du_output = subprocess.check_output(['du', '-sh', image.path])
        size = du_output.decode('utf8').split()[0]
        print(image.name, size)


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
