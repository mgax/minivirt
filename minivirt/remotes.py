import logging
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen

import boto3
import botocore.exceptions
import click

from .configs import Config

logger = logging.getLogger(__name__)


class S3Bucket:
    def __init__(self, name):
        self.name = name
        self.s3 = boto3.client(
            's3',
            endpoint_url=os.environ.get('AWS_ENDPOINT_URL'),
            aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        )

    def exists(self, key):
        try:
            self.s3.head_object(Bucket=self.name, Key=key)

        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False

            raise

        return True

    def upload(self, path, key):
        logger.info('Uploading to %s ...', key)
        self.s3.upload_file(str(path), self.name, key)


class Remotes:
    def __init__(self, db):
        self.db = db
        self.config = Config(self.db.path / 'remotes.json')

    def add(self, name, url):
        self.config[name] = url
        self.config.save()

    def get(self, name):
        url = self.config[name]
        return Remote(self.db, name, url)


class Remote:
    def __init__(self, db, name, url):
        self.db = db
        self.name = name
        self.url = url

    def push(self, image, tag):
        bucket = S3Bucket(self.url.split('/')[-1])
        image_key = f'images/{image.name}.tgz'
        tag_key = f'tags/{tag}'

        with tempfile.TemporaryDirectory() as tmp:
            if not bucket.exists(image_key):
                tar_path = Path(tmp) / 'image.tar'
                tgz_path = Path(tmp) / 'image.tar.gz'
                with tar_path.open('wb') as f:
                    self.db.save(image.name, f)

                subprocess.check_call(['gzip', '-1', tar_path])

                bucket.upload(tgz_path, image_key)

            tag_path = Path(tmp) / 'tag'
            with tag_path.open('w') as f:
                f.write(image.name)

            bucket.upload(tag_path, tag_key)

    def pull(self, tag, local_tag):
        with urlopen(f'{self.url}/tags/{tag}') as f:
            image_id = f.read().decode('utf8')

        if self.db.image_path(image_id).exists():
            logger.info('Image %s already exists', image_id)
            self.db.get_image(image_id).tag(local_tag)
            return

        image_url = f'{self.url}/images/{image_id}.tgz'
        logger.info('Downloading %s from %s ...', local_tag, image_url)
        with subprocess.Popen(
            ['curl', image_url], stdout=subprocess.PIPE
        ) as p:
            self.db.load(local_tag, stdin=p.stdout, gzip=True)


@click.group()
def cli():
    pass


@cli.command()
@click.argument('name')
@click.argument('url')
def add(name, url):
    from minivirt.cli import db

    db.remotes.add(name, url)


@cli.command()
def show():
    from minivirt.cli import db

    for name, url in db.remotes.config.content.items():
        print(name, url)  # noqa
