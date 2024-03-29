import hashlib
import logging
import re
import subprocess
import sys
from time import time

import click

from . import build, qemu, remotes
from .contrib import githubactions
from .db import DB, get_db_path, ImageNotFound
from .exceptions import RemoteNotFound, VmExists, VmIsRunning
from .vms import PortForward, VM

logger = logging.getLogger(__name__)


db = DB(get_db_path())


def parse_port_args(args):
    for arg in args:
        m = re.match(r'(?P<host_port>\d+):(?P<guest_port>\d+)$', arg)
        if m is None:
            raise click.ClickException(f'Can not parse port argument {arg!r}')
        yield PortForward(
            int(m.group('host_port')), int(m.group('guest_port'))
        )


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

    print('All ok')


@cli.command()
@click.argument('image')
@click.argument('name')
@click.option('-m', '--memory', default=1024)
@click.option('--disk', default=None)
@click.option('--port', multiple=True)
def create(image, name, **kwargs):
    if 'port' in kwargs:
        kwargs['ports'] = list(parse_port_args(kwargs.pop('port')))

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
@click.option('--usb', multiple=True)
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
@click.option('--port', multiple=True)
@click.option('--wait-for-ssh', default=60)
@click.argument('image_name')
@click.argument('args', nargs=-1)
def run(memory, port, wait_for_ssh, image_name, args):
    ports = list(parse_port_args(port))
    try:
        image = db.get_image(image_name)
    except ImageNotFound:
        raise click.ClickException(f'Image {image_name!r} not found')
    vm_name = hashlib.sha256(
        f'{image.name}@{time()}'.encode('utf8')
    ).hexdigest()
    vm = VM.create(db, vm_name, image=image, memory=memory, ports=ports)
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
            image.short_name,
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
    logger.info('fsck successful')


@cli.command()
@click.option('-n', '--dry-run', is_flag=True)
def prune(dry_run):
    db.prune(dry_run)


@cli.command()
@click.argument('image_name')
@click.argument('tags', nargs=-1)
def tag(image_name, tags):
    image = db.get_image(image_name)
    for tag in tags:
        image.tag(tag)


@cli.command()
@click.argument('tags', nargs=-1)
def untag(tags):
    for tag in tags:
        db.get_tag(tag).delete()


@cli.command()
@click.argument('remote_name')
@click.argument('ref')
@click.argument('remote_tag')
def push(remote_name, ref, remote_tag):
    try:
        image = db.get_image(ref)
    except ImageNotFound:
        raise click.ClickException(f'Image {ref!r} not found')
    try:
        remote = db.remotes.get(remote_name)
    except RemoteNotFound:
        raise click.ClickException(f'Remote {remote_name!r} not found')
    remote.push(image, remote_tag)


@cli.command()
@click.argument('remote_name')
@click.argument('remote_tag')
@click.argument('tag')
def pull(remote_name, remote_tag, tag):
    try:
        remote = db.remotes.get(remote_name)
    except RemoteNotFound:
        raise click.ClickException(f'Remote {remote_name!r} not found')
    remote.pull(remote_tag.format(arch=qemu.arch), tag)


cli.add_command(remotes.cli, name='remote')
cli.add_command(build.cli, name='build')
cli.add_command(githubactions.cli, name='githubactions')
