import json
import logging
import re
import shutil
from pathlib import Path

import click
import yaml

from . import qemu
from .contrib.alpine import Console
from .utils import waitfor
from .vms import VM

logger = logging.getLogger(__name__)


class ImageTestError(RuntimeError):
    pass


class Builder:
    def __init__(self, db, recipe, verbose):
        self.db = db
        self.recipe = recipe
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

    def console_step(self, step):
        name = step.get('name', '-- unnamed step --')

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

    def build(self):
        iso_url = self.recipe['iso'].format(arch=qemu.arch)

        with self.db.create_image() as creator:
            filename = Path(iso_url).name
            logger.info('Downloading %s ...', filename)
            iso_path = creator.path / filename
            download_path = self.db.cache.get(iso_url)
            shutil.copy(download_path, iso_path)

            config = {
                'iso': filename,
            }
            config_path = creator.path / 'config.json'
            with config_path.open('w') as f:
                json.dump(config, f, indent=2)

        name = '_build'
        self.db.get_vm(name).destroy()
        self.vm = VM.create(
            db=self.db,
            name=name,
            image=creator.image,
            memory=str(self.recipe['memory']),
            disk=str(self.recipe['disk']),
        )

        logger.info('Bootstrapping Alpine %s ...', self.vm)
        with self.vm.run():
            self.console = Console(self.vm.serial_path)
            for step in self.recipe['steps']:
                self.console_step(step)
            waitfor(lambda: not self.vm.qmp_path.exists())

        logger.info('Build finished.')
        self.image = self.vm.commit()
        return self.image

    def test(self):
        for test in self.recipe.get('tests', []):
            test_name = test.get('name')
            logger.info('Running test: %r', test_name)
            test_name = '_test'
            self.db.get_vm(test_name).destroy()
            test_vm = VM.create(
                db=self.db,
                name=test_name,
                image=self.image,
                memory=str(self.recipe['memory']),
            )
            with test_vm.run(wait_for_ssh=30):
                out = test_vm.ssh(test['run'], capture=True)
                logger.debug('Output: %r', out)
                expect = test['expect'].encode('utf8')
                if re.match(expect, out):
                    logger.info('Test %r OK', test_name)
                else:
                    logger.error(
                        'Test %r failed. Expected: %r; output: %r',
                        test_name, expect, out
                    )
                    raise ImageTestError


def build(db, recipe_path, verbose=False):
    with recipe_path.open() as f:
        recipe = yaml.load(f, yaml.Loader)

    builder = Builder(db, recipe, verbose)
    image = builder.build()
    builder.test()
    return image


@click.command
@click.argument(
    'recipe', type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option('--tag')
@click.option('-v', '--verbose', is_flag=True)
def cli(recipe, tag, verbose):
    from minivirt.cli import db

    try:
        image = build(db, recipe, verbose)
    except ImageTestError:
        raise click.ClickException('Build test failed')

    if tag:
        image.tag(tag.format(arch=qemu.arch))

    size = image.get_size()
    print(image.name[:8], size)  # noqa: T201
