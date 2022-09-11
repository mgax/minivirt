import logging
import shutil
import subprocess
from pathlib import Path

import pytest

from minivirt.db import DB
from minivirt.qemu import arch
from minivirt.vms import VM

logger = logging.getLogger(__name__)

CACHE_PATH = Path.home() / '.cache' / 'minivirt-tests'
DB_PATH = CACHE_PATH / 'db'
BASE_IMAGE_URL = (
    f'https://f003.backblazeb2.com/file/minivirt/alpine-3.15.4-{arch}.tgz'
)


@pytest.fixture(scope='session', autouse=True)
def wipe_db():
    if DB_PATH.exists():
        shutil.rmtree(DB_PATH)


@pytest.fixture
def base_image_path():
    path = CACHE_PATH / Path(BASE_IMAGE_URL).name
    if not path.exists():
        logger.info(
            'Base image not present, downloading from %s ...', BASE_IMAGE_URL
        )
        CACHE_PATH.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(['curl', '-sL', BASE_IMAGE_URL, '-o', path])
    assert path.exists()
    return path


@pytest.fixture
def db(base_image_path):
    db = DB(DB_PATH)

    if not db.image_path('base').exists():
        with base_image_path.open('rb') as f:
            db.load('base', stdin=f, gzip=True)

    return db


@pytest.fixture
def vm(db):
    db.get_vm('foo').destroy()
    vm = VM.create(db, 'foo', image=db.get_image('base'), memory=512)
    try:
        yield vm
    finally:
        vm.destroy()
