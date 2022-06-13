import json
import logging
import shutil
import subprocess
import sys
from functools import cached_property

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
        if image_path.exists():
            shutil.rmtree(image_path)

    def vm_path(self, name):
        return self.vms_path / name

    def save(self, name, stdout=sys.stdout):
        subprocess.check_call(
            'tar c *', shell=True, cwd=self.image_path(name), stdout=stdout
        )

    def load(self, name, stdin=sys.stdin, gzip=False):
        image_path = self.image_path(name)
        image_path.mkdir(parents=True)
        flags = 'x'
        if gzip:
            flags += 'z'
        subprocess.check_call(['tar', flags], cwd=image_path, stdin=stdin)

    def iter_images(self):
        for path in self.images_path.iterdir():
            yield Image(self, path.name)

    def iter_vms(self):
        for path in self.vms_path.iterdir():
            yield vms.VM(self, path.name)
