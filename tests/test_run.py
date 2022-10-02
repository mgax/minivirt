from click.testing import CliRunner

from minivirt.cli import cli


def test_run(db, monkeypatch):
    monkeypatch.setattr('minivirt.cli.db', db)
    runner = CliRunner()
    res1 = runner.invoke(cli, ['-v', 'run', 'base'], catch_exceptions=False)
    assert res1.exit_code == 0
