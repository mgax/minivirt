import click

from .configs import Config


class Remotes:
    def __init__(self, db):
        self.db = db
        self.config = Config(self.db.path / 'remotes.json')

    def add(self, name, url):
        self.config[name] = url
        self.config.save()


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
