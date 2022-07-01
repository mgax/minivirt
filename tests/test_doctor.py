from click.testing import CliRunner

from minivirt.cli import cli


def test_doctor():
    runner = CliRunner()
    res = runner.invoke(cli, ['doctor'])
    assert res.exit_code == 0
    assert res.stdout == '🚑👌\n'
