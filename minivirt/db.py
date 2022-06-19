import hashlib
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from functools import cached_property
from io import StringIO
from pathlib import Path

from . import vms

logger = logging.getLogger(__name__)


class Image:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.path = db.image_path(name)
        self.config_path = self.path / 'config.json'

    @cached_property
    def config(self):
        with self.config_path.open() as f:
            return json.load(f)

    @cached_property
    def iso_path(self):
        filename = self.config.get('iso')
        if filename:
            return self.path / filename

    def tag(self, name):
        self.db.image_path(name).symlink_to(self.name)


def file_chunks(path, chunk_size=65536):
    with path.open('rb') as f:
        yield from iter(lambda: f.read(chunk_size), b'')


def checksum(path):
    hash = hashlib.sha256()
    for chunk in file_chunks(path):
        hash.update(chunk)
    return hash.hexdigest()


class ImageCreator:
    def __init__(self, db):
        self.db = db
        db.images_path.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(dir=db.images_path))

    @contextmanager
    def ctx(self):
        try:
            yield self
            self.image = self.commit()

        finally:
            if self.path.exists():
                shutil.rmtree(self.path)

    def commit(self):
        tree = StringIO()
        for path in sorted(self.path.glob('**/*')):
            tree.write(f'{path.relative_to(self.path)}:{checksum(path)}\n')

        tree_checksum = hashlib.sha256(
            tree.getvalue().encode('utf8')
        ).hexdigest()
        image_path = self.db.image_path(tree_checksum)
        if image_path.exists():
            logger.warning('Image {tree_checksum} already exists')
            # TODO check the image's checksum, just to be safe
        else:
            self.path.rename(image_path)
        return self.db.get_image(tree_checksum)


class DB:
    def __init__(self, path):
        self.path = path
        self.images_path = self.path / 'images'
        self.vms_path = self.path / 'vms'

    def image_path(self, filename):
        return self.images_path / filename

    def get_image(self, name):
        return Image(self, name)

    def remove_image(self, name):
        image_path = self.image_path(name)
        if image_path.is_symlink():
            image_path.unlink()

    def create_image(self):
        return ImageCreator(self).ctx()

    def vm_path(self, name):
        return self.vms_path / name

    def get_vm(self, name):
        return vms.VM(self, name)

    def save(self, name, stdout=sys.stdout):
        subprocess.check_call(
            'tar c *', shell=True, cwd=self.image_path(name), stdout=stdout
        )

    def load(self, name, stdin=sys.stdin, gzip=False):
        with self.create_image() as creator:
            flags = 'x'
            if gzip:
                flags += 'z'
            subprocess.check_call(
                ['tar', flags], cwd=creator.path, stdin=stdin
            )
        creator.image.tag(name)

    def iter_images(self):
        for path in self.images_path.iterdir():
            yield Image(self, path.name)

    def iter_vms(self):
        for path in self.vms_path.iterdir():
            yield vms.VM(self, path.name)
