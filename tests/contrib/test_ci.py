import pytest
from click.testing import CliRunner

from minivirt.cli import cli


@pytest.mark.arch('x86_64')
@pytest.mark.slow
def test_build(db, monkeypatch):
    monkeypatch.setattr('minivirt.cli.db', db)
    runner = CliRunner()

    res1 = runner.invoke(cli, ['ci', 'build', 'base', 'foo'])
    assert res1.exit_code == 0

    foo = db.get_vm('foo')
    with foo.run(wait_for_ssh=30):
        assert foo.ssh('dotnet --info', capture=True).startswith(b'.NET SDK')

        assert foo.ssh(
            'grep ^root /etc/passwd', capture=True
        ).strip().endswith(b'/bin/bash')

        assert foo.ssh(
            'ls -l /dev/kvm', capture=True
        ).strip().endswith(b'/dev/kvm')

        assert foo.ssh(
            'qemu-system-x86_64 -version', capture=True
        ).startswith(b'QEMU emulator version')

    foo.destroy()
