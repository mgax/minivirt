import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from functools import cached_property
from io import StringIO
from pathlib import Path

from . import vms
from .cache import Cache
from .remotes import Remotes

logger = logging.getLogger(__name__)


class Image:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        assert re.match(r'^[0-9a-f]{64}$', name)
        self.path = db.image_path(name)
        self.config_path = self.path / 'config.json'

    def __repr__(self):
        return f'<Image {self.name[:8]}>'

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
        tag_path = self.db.image_path(name)
        target = Path(self.name)
        if tag_path.is_symlink():
            old_target = Path(os.readlink(tag_path))
            if old_target == target:
                return
            logger.warning('Overwriting tag %s -> %s', name, old_target.name)
            tag_path.unlink()
        tag_path.symlink_to(target)

    def iter_tags(self):
        for tag in self.db.iter_tags():
            if tag.image_id == self.name:
                yield tag

    def fsck(self):
        if tree_checksum(self.path) != self.name:
            yield 'invalid checksum'

    def get_size(self):
        du_output = subprocess.check_output(['du', '-sh', self.path])
        return du_output.decode('utf8').split()[0]

    def delete(self):
        shutil.rmtree(self.path)


class Tag:
    def __init__(self, db, name):
        self.db = db
        self.name = name

    @cached_property
    def path(self):
        return self.db.images_path / self.name

    @cached_property
    def image_id(self):
        return self.path.resolve().name

    def delete(self):
        self.path.unlink()

    def fsck(self):
        if not (self.db.images_path / self.image_id).exists():
            yield 'target image does not exist'


def file_chunks(path, chunk_size=65536):
    with path.open('rb') as f:
        yield from iter(lambda: f.read(chunk_size), b'')


def checksum(path):
    hash = hashlib.sha256()
    for chunk in file_chunks(path):
        hash.update(chunk)
    return hash.hexdigest()


def tree_checksum(path):
    tree = StringIO()
    for file_path in sorted(path.glob('**/*')):
        tree.write(f'{file_path.relative_to(path)}:{checksum(file_path)}\n')
    return hashlib.sha256(tree.getvalue().encode('utf8')).hexdigest()


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
        image_id = tree_checksum(self.path)
        image_path = self.db.image_path(image_id)
        if image_path.exists():
            logger.warning('Image %s already exists', image_id)
            # TODO check the image's checksum, just to be safe
        else:
            self.path.rename(image_path)
        logger.info('Committed image %s', image_id)
        return self.db.get_image(image_id)


class FsckResult:
    def __init__(self):
        self.errors = []


class ImageNotFound(Exception):
    pass


class DB:
    def __init__(self, path):
        self.path = path
        self.images_path = self.path / 'images'
        self.vms_path = self.path / 'vms'
        self.remotes = Remotes(self)

    @cached_property
    def cache(self):
        cache_path = self.path / 'cache'
        cache_path.mkdir(parents=True, exist_ok=True)
        return Cache(cache_path)

    def image_path(self, filename):
        return self.images_path / filename

    def get_image(self, name):
        path = self.images_path / name
        if path.is_symlink():
            name = path.resolve().name
        if not (self.images_path / name).exists():
            raise ImageNotFound
        return Image(self, name)

    def remove_image(self, name):
        image_path = self.image_path(name)
        if image_path.is_symlink():
            image_path.unlink()

    def create_image(self):
        return ImageCreator(self).ctx()

    def get_tag(self, name):
        return Tag(self, name)

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
        for path in self.images_path.glob('*'):
            if path.is_symlink():
                continue
            yield Image(self, path.name)

    def iter_tags(self):
        for path in self.images_path.glob('*'):
            if not path.is_symlink():
                continue
            yield Tag(self, path.name)

    def iter_vms(self):
        for path in self.vms_path.glob('*'):
            yield vms.VM(self, path.name)

    def fsck(self):
        result = FsckResult()

        for image in self.iter_images():
            for error in image.fsck():
                result.errors.append(f'{image}: {error}')

        for tag in self.iter_tags():
            for error in tag.fsck():
                result.errors.append(f'{tag}: {error}')

        for vm in self.iter_vms():
            for error in vm.fsck():
                result.errors.append(f'{vm}: {error}')

        return result

    def prune(self, dry_run=False):
        keep = set()
        for tag in self.iter_tags():
            logger.debug(
                'Prune keeping %s tagged as %s', tag.image_id, tag.name
            )
            keep.add(tag.image_id)

        for vm in self.iter_vms():
            if vm.image:
                logger.debug(
                    'Prune keeping %s for vm %s', vm.image.name, vm.name
                )
                keep.add(vm.image.name)

        for image in self.iter_images():
            if image.name not in keep:
                logger.info('Removing %s', image.name)
                if not dry_run:
                    image.delete()
