import sys
from pathlib import Path
import subprocess
import logging
import json
from functools import cached_property

ALPINE_ISO_URL = (
    'https://dl-cdn.alpinelinux.org/alpine/v3.15/releases/aarch64/'
    'alpine-standard-3.15.4-aarch64.iso'
)

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
        self.path.mkdir(parents=True, exist_ok=True)

    def image_path(self, filename):
        return self.path / filename

    def get_image(self, name):
        return Image(self, name)

    def vm_path(self, name):
        return self.path / name

    def download_alpine(self):
        image_path = self.image_path('alpine')
        assert not image_path.exists()
        image_path.mkdir(parents=True)

        filename = Path(ALPINE_ISO_URL).name
        logger.info('Downloading %s ...', filename)
        iso_path = image_path / filename
        subprocess.check_call(['curl', '-L', ALPINE_ISO_URL, '-o', iso_path])

        config = {
            'iso': filename,
        }
        config_path = image_path / 'config.json'
        with config_path.open('w') as f:
            json.dump(config, f, indent=2)

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
