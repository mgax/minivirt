import hashlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from time import time

import click

from . import build, qemu, remotes
from .contrib import githubactions
from .db import DB, ImageNotFound
from .exceptions import VmExists, VmIsRunning
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
@click.option('-m', '--memory', default=1024)
@click.option('--disk', default=None)
def create(image, name, **kwargs):
    try:
        image = db.get_image(image)
    except ImageNotFound:
        raise click.ClickException(f'Image {image!r} not found')

    try:
        VM.create(db, name, image=image, **kwargs)
    except VmExists:
        raise click.ClickException(f'VM {name!r} already exists')


@cli.command()
@click.argument('name')
@click.option('--daemon', is_flag=True)
@click.option('--display', is_flag=True)
@click.option('--snapshot', is_flag=True)
@click.option('--wait-for-ssh', type=int, default=None)
def start(name, **kwargs):
    vm = db.get_vm(name)
    try:
        vm.start(**kwargs)
    except VmIsRunning:
        raise click.ClickException(f'{vm} is already running')


@cli.command()
@click.argument('name')
def stop(name):
    vm = db.get_vm(name)
    vm.stop()


@cli.command()
@click.argument('name')
def kill(name):
    vm = db.get_vm(name)
    vm.kill()


@cli.command()
@click.argument('name')
def destroy(name):
    vm = db.get_vm(name)
    vm.destroy()


@cli.command()
@click.argument('name')
def console(name):
    vm = db.get_vm(name)
    vm.console()


@cli.command()
@click.argument('name')
@click.argument('args', nargs=-1)
def ssh(name, args):
    vm = db.get_vm(name)
    vm.ssh(*args)


@cli.command()
@click.option('-m', '--memory', default=1024)
@click.option('--wait-for-ssh', default=30)
@click.argument('image_name')
@click.argument('args', nargs=-1)
def run(memory, wait_for_ssh, image_name, args):
    try:
        image = db.get_image(image_name)
    except ImageNotFound:
        raise click.ClickException(f'Image {image_name!r} not found')
    vm_name = hashlib.sha256(
        f'{image.name}@{time()}'.encode('utf8')
    ).hexdigest()
    vm = VM.create(db, vm_name, image=image, memory=memory)
    try:
        with vm.run(wait_for_ssh=wait_for_ssh):
            vm.ssh(*args)
    finally:
        vm.destroy()


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
        size = image.get_size()
        print(
            image.name[:8],
            size,
            ' '.join(tag.name for tag in image.iter_tags()),
        )


@cli.command()
@click.argument('name')
@click.argument('tag')
def commit(name, tag):
    vm = db.get_vm(name)
    image = vm.commit()
    image.tag(tag)


@cli.command()
@click.argument('image')
def save(image):
    db.save(image)


@cli.command()
@click.argument('image')
def load(image):
    db.load(image)


@cli.command()
def fsck():
    result = db.fsck()
    for message in result.errors:
        logger.warning('fsck error: %s', message)
    if result.errors:
        sys.exit(1)
    print('🩺👌')


@cli.command()
@click.option('-n', '--dry-run', is_flag=True)
def prune(dry_run):
    db.prune(dry_run)


@cli.command()
@click.argument('name')
def untag(name):
    db.get_tag(name).delete()


@cli.command()
@click.argument('remote')
@click.argument('ref')
@click.argument('remote_tag')
def push(remote, ref, remote_tag):
    image = db.get_image(ref)
    db.remotes.get(remote).push(image, remote_tag)


@cli.command()
@click.argument('remote')
@click.argument('remote_tag')
@click.argument('tag')
def pull(remote, remote_tag, tag):
    db.remotes.get(remote).pull(remote_tag.format(arch=qemu.arch), tag)


cli.add_command(remotes.cli, name='remote')
cli.add_command(build.cli, name='build')
cli.add_command(githubactions.cli, name='githubactions')
