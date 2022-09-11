import pytest
from click.testing import CliRunner

from minivirt.cli import cli
from minivirt.vms import VM


@pytest.mark.slow
def test_bootstrap(db, monkeypatch):
    monkeypatch.setattr('minivirt.cli.db', db)
    runner = CliRunner()

    res1 = runner.invoke(cli, ['alpine', 'download', '3.15.4', 'alpine-iso'])
    assert res1.exit_code == 0

    res2 = runner.invoke(
        cli, ['alpine', 'install', 'alpine-iso', 'foo', '10G']
    )
    assert res2.exit_code == 0

    res3 = runner.invoke(
        cli, ['start', 'foo', '--daemon', '--wait-for-ssh=10']
    )
    assert res3.exit_code == 0

    foo = db.get_vm('foo')
    foo.ssh('poweroff')
    foo.wait()

    image = foo.commit()
    db.remove_image('alpine-iso')
    foo.destroy()

    bar = VM.create(db, 'bar', image=image, memory=512)
    with bar.run(wait_for_ssh=30):
        assert bar.ssh('uname -a', capture=True).startswith(b'Linux alpine')
    bar.destroy()
