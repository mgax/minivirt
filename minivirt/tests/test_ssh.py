import subprocess
from pathlib import Path
import os
import shutil
import logging

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


def test_connect_with_ssh(db):
    foo_path = db.vm_path('foo')
    if foo_path.exists():
        shutil.rmtree(foo_path)
    vm = VM.create(db, 'foo', db.get_image('base'))
    with vm.run(wait_for_ssh=True):
        ssh_config = Path(__file__).parent / 'ssh_config'
        out = subprocess.check_output(
            ['ssh', '-F', ssh_config, 'foo.minivirt', 'hostname']
        )
    assert out.strip() == b'alpine'
