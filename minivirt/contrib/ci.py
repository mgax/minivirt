import logging
import shlex

import click

from minivirt.vms import VM

logger = logging.getLogger(__name__)

GITHUB_RUNNER_URL = (
    'https://github.com/actions/runner/releases/download/'
    'v2.293.0/actions-runner-linux-x64-2.293.0.tar.gz'
)


@click.group()
def cli():
    pass


@cli.command()
@click.argument('image')
@click.argument('name')
@click.option('--memory', default=1024)
def build(image, name, memory):
    from minivirt.cli import db

    packages = [
        'py3-pip',
        'qemu',
        'qemu-system-x86_64',
        'qemu-img',
        'socat',
        'tar',
        'git',
        'bash',
        'vim',
        'gcompat',
        'icu',
    ]
    apk_sed = r's|# \(http://dl-cdn.alpinelinux.org/alpine/.*/community\)|\1|'
    login_shell_sed = r's|\(root:x:0:0:root:/root:\)/bin/ash|\1/bin/bash|'

    vm = VM.create(db, name, db.get_image(image), memory=memory)
    with vm.run(wait_for_ssh=30):
        vm.ssh(f'sed -i {shlex.quote(apk_sed)} /etc/apk/repositories')
        vm.ssh(f'apk add {" ".join(packages)}')
        vm.ssh(f'sed -i {shlex.quote(login_shell_sed)} /etc/passwd')
        vm.ssh('curl -LOs https://dot.net/v1/dotnet-install.sh')
        vm.ssh('bash dotnet-install.sh -c 6.0')
        vm.ssh('ln -s /root/.dotnet/dotnet /usr/local/bin')
        vm.ssh('poweroff')
        vm.wait()


@cli.command()
@click.argument('name')
def testsuite(name):
    from minivirt.cli import db

    vm = db.get_vm(name)
    with vm.run(wait_for_ssh=30, snapshot=True):
        vm.ssh('git clone https://github.com/mgax/minivirt')
        vm.ssh('pip3 install ./minivirt')
        vm.ssh('pip3 install pytest')
        vm.ssh('miv doctor')
        vm.ssh('cd minivirt; pytest -vv')


@cli.command()
@click.argument('name')
@click.argument('repo')
@click.argument('token')
def setup_github_runner(name, repo, token):
    from minivirt.cli import db

    vm = db.get_vm(name)
    with vm.run(wait_for_ssh=30):
        vm.ssh(
            f'mkdir actions-runner && cd actions-runner'
            f' && curl -Ls {GITHUB_RUNNER_URL} | tar xz'
            f' && ./bin/Runner.Listener configure'
            f'      --url {repo}'
            f'      --token {token}'
            f'      --unattended'
        )
        vm.ssh('poweroff')
        vm.wait()
