import os
import logging
from pathlib import Path
import subprocess

import pytest

from minivirt.db import DB
from minivirt.vms import VM

logger = logging.getLogger(__name__)


@pytest.fixture
def db():
    cache = Path.home() / '.cache' / 'minivirt-tests'
    cache.mkdir(parents=True, exist_ok=True)
    db = DB(cache / 'db')

    if not db.image_path('base').exists():
        base_image_url = os.environ['MINIVIRT_TESTING_IMAGE_URL']
        logger.info(
            'Base image not present, downloading from %s ...', base_image_url
        )
        with subprocess.Popen(
            ['curl', '-sL', base_image_url], stdout=subprocess.PIPE
        ) as curl:
            db.load('base', stdin=curl.stdout, gzip=True)

    return db


@pytest.fixture
def vm(db):
    VM.open(db, 'foo').destroy()
    vm = VM.create(db, 'foo', db.get_image('base'))
    try:
        yield vm
    finally:
        vm.destroy()


@pytest.fixture
def ssh():
    def ssh(vm, command):
        ssh_config = Path(__file__).parent / 'ssh_config'
        return subprocess.check_output(
            ['ssh', '-F', ssh_config, f'{vm.name}.minivirt', command]
        )

    return ssh
