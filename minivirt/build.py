import logging
import re
import shutil
import subprocess
from pathlib import Path

import click
import yaml

from . import qemu
from .contrib.alpine import Console
from .utils import waitfor
from .vms import VM

logger = logging.getLogger(__name__)

BUILD_STEPS = {}


def build_step(func):
    BUILD_STEPS[func.__name__] = func
    return func


def attach_to_vm(builder, filename, type):
    if type == 'disk':
        builder.vm.attach_disk(filename)
    elif type == 'cdrom':
        builder.vm.attach_cdrom(filename)
    else:
        raise RuntimeError('Unknown attachment type')


@build_step
def create_disk_image(builder, size, attach=None, filename='disk.qcow2'):
    path = builder.vm.path / filename
    assert not path.exists()
    subprocess.check_call(['qemu-img', 'create', '-f', 'qcow2', path, size])

    if attach:
        attach_to_vm(builder, filename, **attach)


@build_step
def download(builder, url, attach=None, filename=None):
    url = url.format(arch=qemu.arch)
    if filename is None:
        filename = url.split('/')[-1]
    path = builder.vm.path / filename
    assert not path.exists()
    cache_path = builder.db.cache.get(url)
    shutil.copy(cache_path, path)

    if attach:
        attach_to_vm(builder, filename, **attach)


@build_step
def run_with_serial_console(builder, steps):
    with builder.vm.run():
        builder.console = Console(builder.vm.serial_path)
        for step in steps:
            builder.console_step(step)
        waitfor(lambda: not builder.vm.qmp_path.exists())


@build_step
def detach(builder, filename):
    resources = builder.vm.config['resources']
    for item in list(resources):
        if item.get('filename') == filename:
            resources.remove(item)
            builder.vm.config.save()


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

    def build_step(self, step):
        func = BUILD_STEPS[step['uses']]
        func(self, **step['with'])

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
        name = '_build'
        self.db.get_vm(name).destroy()
        self.vm = VM.create(
            db=self.db,
            name=name,
            memory=str(self.recipe['memory']),
        )

        for step in self.recipe['steps']:
            self.build_step(step)

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
