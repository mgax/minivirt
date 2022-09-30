import json
import logging
import socket
import subprocess
from contextlib import closing

import click
import waitress
from github import Github
from pyngrok import ngrok

logger = logging.getLogger(__name__)


def find_free_port():  # https://stackoverflow.com/a/45690594
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def fetch_github_token():
    out = subprocess.check_output(
        "echo 'protocol=https\\nhost=github.com' | git credential fill",
        shell=True
    )
    token = out.decode('utf8').splitlines()[-1].split('=')[1]
    assert token[:4] == 'ghp_'
    return token


def create_webhook(github_token, repo, url):
    config = dict(url=url, content_type='json')
    events = ['ping']
    g = Github(github_token)
    repo = g.get_repo(repo)
    return repo.create_hook('web', config, events, active=True)


class Webhook:

    def __call__(self, environ, start_response):
        def respond(status, data):
            start_response(status, [('Content-Type', 'text/plain')])
            return [data.encode('utf8')]

        try:
            # TODO check X-Hub-Signature headers
            event = environ.get('HTTP_X_GITHUB_EVENT')
            payload = json.load(environ['wsgi.input'])
            handler = getattr(self, f'handle_{event}')
            body = handler(payload)

        except Exception:
            logger.exception('Error processing wsgi request')
            return respond('500 Internal Server Error', 'internal error')

        else:
            return respond('200 OK', body)

    def handle_ping(self, payload):
        logger.info('Webhook ping: %s', payload['zen'])
        return 'pong'


@click.group()
def cli():
    logging.getLogger('pyngrok').setLevel(logging.WARNING)


@cli.command()
@click.argument('repo')
def serve(repo):
    github_token = fetch_github_token()
    port = find_free_port()
    listen = f'127.0.0.1:{port}'
    tunnel = ngrok.connect(port, bind_tls=True)
    logger.info('ngrok tunnel %s', tunnel.public_url)

    webhook = create_webhook(github_token, repo, tunnel.public_url)

    try:
        waitress.serve(Webhook(), listen=listen)

    finally:
        webhook.delete()
