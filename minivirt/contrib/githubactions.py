import json
import logging
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from time import time

import click

from minivirt.vms import VM

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


def github_repo_api(token, repo):
    from github import Github

    return Github(token).get_repo(repo)


def create_webhook(repo, url):
    config = dict(url=url, content_type='json')
    events = ['ping', 'workflow_job']
    return repo.create_hook('web', config, events, active=True)


def runner(github_repo):
    from minivirt.cli import db
    from minivirt.contrib.ci import GITHUB_RUNNER_URL

    logger.info('Fetching runner registration token')
    _, data = github_repo._requester.requestJsonAndCheck(
        'POST', f'{github_repo.url}/actions/runners/registration-token'
    )
    registration_token = data['token']

    vm_name = f'githubactions_{time()}'.replace('.', '_')
    image = db.get_image('githubactions')
    logger.info('Creating VM %s', vm_name)
    vm = VM.create(db, vm_name, image=image, memory=512)
    try:
        with vm.run(wait_for_ssh=30):
            vm.ssh(
                # TODO move the runner installation to the image
                f'mkdir actions-runner && cd actions-runner'
                f' && curl -Ls {GITHUB_RUNNER_URL} | tar xz'
                f' && ./bin/Runner.Listener configure'
                f'      --url {github_repo.html_url}'
                f'      --token {registration_token}'
                f'      --ephemeral'
                f'      --unattended'
            )
            logger.info('Starting runner')
            vm.ssh(
                'RUNNER_ALLOW_RUNASROOT=yes /root/actions-runner/run.sh'
            )

    finally:
        vm.destroy()


class Webhook:

    def __init__(self, start_runner):
        self.start_runner = start_runner

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

    def handle_workflow_job(self, payload):
        job = payload['workflow_job']
        action = payload['action']
        logger.info('Webhook workflow job: %s %s', job['run_id'], action)
        if action == 'queued':
            self.start_runner()
        return 'thanks'


@click.group()
def cli():
    logging.getLogger('pyngrok').setLevel(logging.WARNING)


@cli.command()
@click.argument('repo')
def serve(repo):
    import waitress
    from pyngrok import ngrok

    github_repo = github_repo_api(fetch_github_token(), repo)
    port = find_free_port()
    listen = f'127.0.0.1:{port}'
    tunnel = ngrok.connect(port, bind_tls=True)
    logger.info('ngrok tunnel %s', tunnel.public_url)

    webhook = create_webhook(github_repo, tunnel.public_url)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            def start_runner():
                executor.submit(runner, github_repo)

            wsgi_app = Webhook(start_runner)
            waitress.serve(wsgi_app, listen=listen)

    finally:
        webhook.delete()
