import re
import subprocess
import sys

import click


@click.group()
def cli():
    pass


VM_UNIT = '''\
[Unit]
Description=MiniVirt VM {name}
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User={uid}
Group={gid}
ExecStart={miv} start {name} --daemon --wait-for-ssh=30
ExecStop={miv} stop {name}

[Install]
WantedBy=multi-user.target
'''


COMMAND_UNIT = '''\
[Unit]
Description=MiniVirt Command {name} {args_txt}
After=minivirt-{name}
Wants=minivirt-{name}

[Service]
User={uid}
Group={gid}
ExecStart=ssh {name}.miv {args_txt}

[Install]
WantedBy=multi-user.target
'''


def uidgid():
    out = subprocess.check_output(['id'])
    return {
        m.group('key'): m.group('value')
        for m in (
            re.match(r'^(?P<key>\w+)=\d+\((?P<value>\w+)\)$', item)
            for item in out.decode('utf8').split()
        ) if m
    }


@cli.command()
@click.argument('name')
def vm_unit(name):
    sys.stdout.write(VM_UNIT.format(name=name, miv=sys.argv[0], **uidgid()))


@cli.command()
@click.argument('name')
@click.argument('args', nargs=-1)
def command_unit(name, args):
    sys.stdout.write(
        COMMAND_UNIT.format(name=name, args_txt=' '.join(args), **uidgid())
    )
