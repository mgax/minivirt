import hmac
import json
import logging
import os
import secrets
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


def create_webhook(repo, url, secret):
    config = dict(url=url, content_type='json', secret=secret)
    events = ['ping', 'workflow_job']
    return repo.create_hook('web', config, events, active=True)


def get_workflow_run_jobs(run):
    headers, data = run._requester.requestJsonAndCheck('GET', run.jobs_url)
    yield from data['jobs']


def _random_name(prefix):
    return f'{prefix}_{str(time()).replace(".", "_")}'


def log_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception('Exception in runner thread')

    return wrapper


@log_errors
def runner(image_name, github_repo, memory):
    from minivirt.cli import db

    logger.debug('Fetching runner registration token')
    _, data = github_repo._requester.requestJsonAndCheck(
        'POST', f'{github_repo.url}/actions/runners/registration-token'
    )
    registration_token = data['token']

    vm_name = _random_name('githubactions')
    image = db.get_image(image_name)
    logger.info('Runner %s creating', vm_name)
    vm = VM.create(db, vm_name, image=image, memory=memory)
    try:
        with vm.run(wait_for_ssh=30):
            vm.ssh(
                f'/root/actions-runner/bin/Runner.Listener configure'
                f' --url {github_repo.html_url}'
                f' --token {registration_token}'
                f' --name {vm_name}'
                f' --ephemeral'
                f' --unattended'
                f' --disableupdate'
            )
            logger.info('Runner %s starting', vm_name)
            vm.ssh('poweroff -d 1800 > /dev/null 2>/dev/null &')
            vm.ssh('RUNNER_ALLOW_RUNASROOT=yes /root/actions-runner/run.sh')

    finally:
        logger.info('Runner %s done', vm_name)
        vm.destroy()


class Webhook:

    def __init__(self, secret, start_runner):
        self.secret = secret
        self.start_runner = start_runner

    def __call__(self, environ, start_response):
        def respond(status, data):
            start_response(status, [('Content-Type', 'text/plain')])
            return [data.encode('utf8')]

        try:
            event = environ.get('HTTP_X_GITHUB_EVENT')
            signature = environ.get('HTTP_X_HUB_SIGNATURE_256')
            payload_bytes = environ['wsgi.input'].read()
            if not self.check(signature, payload_bytes):
                logger.warning('Signature check failed')
                return respond('400 Bad Request', 'bad signature')
            payload = json.loads(payload_bytes)
            handler = getattr(self, f'handle_{event}')
            body = handler(payload)

        except Exception:
            logger.exception('Error processing wsgi request')
            return respond('500 Internal Server Error', 'internal error')

        else:
            return respond('200 OK', body)

    def check(self, signature, payload_bytes):
        assert signature.startswith('sha256=')
        digest = hmac.HMAC(
            self.secret.encode('utf8'), payload_bytes, 'sha256'
        ).hexdigest()
        return hmac.compare_digest(signature.split('=')[1], digest)

    def handle_ping(self, payload):
        logger.info('Webhook ping: %s', payload['zen'])
        return 'pong'

    def handle_workflow_job(self, payload):
        job = payload['workflow_job']
        action = payload['action']
        logger.info(
            'Job %s %s %s', action, job['runner_name'], job['html_url']
        )
        if action == 'queued':
            self.start_runner()
        return 'thanks'


@click.group()
def cli():
    logging.getLogger('pyngrok').setLevel(logging.WARNING)


def start_ngrok_tunnel(port):
    from pyngrok import ngrok

    token = os.environ.get('NGROK_AUTH_TOKEN')
    if token:
        ngrok.set_auth_token(token)
    else:
        logger.warning('No ngrok token. The public URL will time out.')
    tunnel = ngrok.connect(port, bind_tls=True)
    logger.info('ngrok tunnel %s', tunnel.public_url)

    return tunnel


@cli.command()
@click.argument('image')
@click.argument('repo')
@click.option('-m', '--memory', default=1024)
@click.option('--concurrency', default=1)
def serve(image, repo, memory, concurrency):
    import waitress

    github_repo = github_repo_api(fetch_github_token(), repo)
    port = find_free_port()
    listen = f'127.0.0.1:{port}'
    tunnel = start_ngrok_tunnel(port)

    secret = secrets.token_hex()
    webhook = create_webhook(github_repo, tunnel.public_url, secret)

    try:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            def start_runner():
                executor.submit(runner, image, github_repo, memory)

            for run in github_repo.get_workflow_runs(status='queued'):
                for job in get_workflow_run_jobs(run):
                    if job['status'] == 'queued':
                        logger.info('Queueing runner for %s', job['html_url'])
                        start_runner()

            wsgi_app = Webhook(secret, start_runner)
            waitress.serve(wsgi_app, listen=listen)

    finally:
        webhook.delete()
