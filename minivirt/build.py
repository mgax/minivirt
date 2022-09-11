import json
import logging
import shutil
from pathlib import Path

import click
import yaml

from . import qemu
from .contrib.alpine import Console
from .utils import waitfor
from .vms import VM

logger = logging.getLogger(__name__)


class Builder:
    def __init__(self, vm, verbose):
        self.vm = vm
        self.verbose = verbose

    def wait(self, pattern, **kwargs):
        logger.debug('Waiting for pattern: %r', pattern)
        output = self.console.wait_for_pattern(
            pattern, verbose=self.verbose, **kwargs
        )
        logger.info('Received: %r', output)
        return output

    def send(self, message):
        logger.info('Sending: %r', message)
        self.console.send(message)

    def step(self, step):
        name = step['name']

        if 'if_arch' in step:
            if qemu.arch != step['if_arch']:
                logger.info('Skipping step: %r', name)
                return

        if name:
            logger.info('Step: %r', name)

        if 'send' in step:
            self.send(step['send'].encode('utf8'))

        if 'wait' in step:
            kwargs = {}
            if 'timeout' in step:
                kwargs['timeout'] = step['timeout']
            self.wait(step['wait'].encode('utf8'), **kwargs)

    def build(self, steps):
        logger.info('Bootstrapping Alpine %s ...', self.vm)
        with self.vm.run():
            self.console = Console(self.vm.serial_path)
            for step in steps:
                self.step(step)
            waitfor(lambda: not self.vm.qmp_path.exists())

        logger.info('Build finished.')

        return self.vm


def build(db, recipe_path, verbose):
    with recipe_path.open() as f:
        recipe = yaml.load(f, yaml.Loader)

    iso_url = recipe['iso'].format(arch=qemu.arch)

    with db.create_image() as creator:
        filename = Path(iso_url).name
        logger.info('Downloading %s ...', filename)
        iso_path = creator.path / filename
        download_path = db.cache.get(iso_url)
        shutil.copy(download_path, iso_path)

        config = {
            'iso': filename,
        }
        config_path = creator.path / 'config.json'
        with config_path.open('w') as f:
            json.dump(config, f, indent=2)

    name = '_build'
    db.get_vm(name).destroy()
    vm = VM.create(
        db=db,
        name=name,
        image=creator.image,
        memory=str(recipe['memory']),
        disk=str(recipe['disk']),
    )

    return Builder(vm, verbose).build(recipe['steps'])


@click.command
@click.argument(
    'recipe', type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option('--tag')
@click.option('-v', '--verbose', is_flag=True)
def cli(recipe, tag, verbose):
    from minivirt.cli import db

    vm = build(db, recipe, verbose)

    if tag:
        vm.commit(tag.format(arch=qemu.arch))
