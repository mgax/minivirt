import logging
import os
import subprocess
from pathlib import Path

import pytest

from minivirt.db import DB
from minivirt.vms import VM

logger = logging.getLogger(__name__)

CACHE_PATH = Path.home() / '.cache' / 'minivirt-tests'
BASE_IMAGE_URL = os.environ['MINIVIRT_TESTING_IMAGE_URL']


@pytest.fixture
def base_image_path():
    path = CACHE_PATH / Path(BASE_IMAGE_URL).name
    if not path.exists():
        logger.info(
            'Base image not present, downloading from %s ...', BASE_IMAGE_URL
        )
        subprocess.check_call(['curl', '-sL', BASE_IMAGE_URL, '-o', path])
    assert path.exists()
    return path


@pytest.fixture
def db(base_image_path):
    CACHE_PATH.mkdir(parents=True, exist_ok=True)
    db = DB(CACHE_PATH / 'db')

    if not db.image_path('base').exists():
        with base_image_path.open('rb') as f:
            db.load('base', stdin=f, gzip=True)

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
            ['ssh', '-F', ssh_config, f'{vm.name}.miv', command]
        )

    return ssh
