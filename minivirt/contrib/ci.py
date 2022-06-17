import logging
import shlex
import subprocess

import click

from minivirt.vms import VM

logger = logging.getLogger(__name__)


def ssh(vm, command):
    logger.info('Running %r', command)
    subprocess.check_call(['ssh', f'{vm.name}.miv', command])


@click.group()
def cli():
    pass


@cli.command()
@click.argument('image')
@click.argument('name')
def build(image, name):
    from minivirt.cli import db

    sed_rule = r's|# \(http://dl-cdn.alpinelinux.org/alpine/.*/community\)|\1|'
    packages = [
        'py3-pip',
        'qemu',
        'qemu-system-x86_64',
        'qemu-img',
        'socat',
        'tar',
        'git',
    ]

    vm = VM.create(db, name, db.get_image(image), memory=1024)
    with vm.run(wait_for_ssh=30):
        ssh(vm, f'sed -i {shlex.quote(sed_rule)} /etc/apk/repositories')
        ssh(vm, f'apk add {" ".join(packages)}')
        ssh(vm, 'poweroff')
        vm.wait()


@cli.command()
@click.argument('name')
def testsuite(name):
    from minivirt.cli import db

    vm = VM.open(db, name)
    with vm.run(wait_for_ssh=30, snapshot=True):
        ssh(vm, 'git clone https://github.com/mgax/minivirt')
        ssh(vm, 'pip3 install ./minivirt')
        ssh(vm, 'pip3 install pytest')
        ssh(vm, 'miv doctor')
        ssh(vm, 'cd minivirt; pytest -vv')


@cli.command()
@click.argument('name')
def install_github_runner(name):
    from minivirt.cli import db

    packages = [
        'bash',
        'vim',
        'gcompat',
        'icu',
    ]
    sed_rule = r's|\(root:x:0:0:root:/root:\)/bin/ash|\1/bin/bash|'
    github_runner_url = (
        'https://github.com/actions/runner/releases/download/'
        'v2.293.0/actions-runner-linux-x64-2.293.0.tar.gz'
    )

    vm = VM.open(db, name)
    with vm.run(wait_for_ssh=30):
        ssh(vm, f'apk add {" ".join(packages)}')
        ssh(vm, f'sed -i {shlex.quote(sed_rule)} /etc/passwd')
        ssh(vm, 'curl -LOs https://dot.net/v1/dotnet-install.sh')
        ssh(vm, 'bash dotnet-install.sh -c 6.0')
        ssh(vm, 'ln -s /root/.dotnet/dotnet /usr/local/bin')
        ssh(vm, 'mkdir actions-runner')
        ssh(vm, f'cd actions-runner'
                f' && curl -Ls {github_runner_url} | tar xz')
        ssh(vm, 'poweroff')
        vm.wait()


@cli.command()
@click.argument('name')
@click.argument('repo')
@click.argument('token')
def setup_github_runner(name, repo, token):
    from minivirt.cli import db

    vm = VM.open(db, name)
    with vm.run(wait_for_ssh=30):
        ssh(
            vm,
            f'cd actions-runner'
            f' && ./bin/Runner.Listener configure'
            f'      --url {repo}'
            f'      --token {token}'
            f'      --unattended'
        )
        ssh(vm, 'poweroff')
        vm.wait()
