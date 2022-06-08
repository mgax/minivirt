import subprocess

import click


@click.group()
def cli():
    pass


@cli.command()
def doctor():
    qemu_version = subprocess.check_output(
        ['qemu-system-aarch64', '--version']
    )
    assert qemu_version.startswith(b'QEMU emulator version')
    print('🚑👌')


cli()
