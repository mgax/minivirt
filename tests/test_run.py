from contextlib import contextmanager

from _pytest.capture import FDCapture
from click.testing import CliRunner

from minivirt.cli import cli


@contextmanager
def capture_fd(fd):
    capture = FDCapture(fd)
    capture.start()
    try:
        yield capture
    finally:
        capture.done()


def test_run(db, monkeypatch):
    monkeypatch.setattr('minivirt.cli.db', db)
    runner = CliRunner()
    cmd = ['-v', 'run', '--memory=512', 'base']
    res1 = runner.invoke(cli, cmd, catch_exceptions=False)
    assert res1.exit_code == 0


def test_run_with_arguments(db, monkeypatch):
    monkeypatch.setattr('minivirt.cli.db', db)
    runner = CliRunner()
    with capture_fd(1) as capture:
        cmd = ['-v', 'run', '--memory=512', 'base', 'hostname']
        res1 = runner.invoke(cli, cmd, catch_exceptions=False)
        assert res1.exit_code == 0
        output = capture.snap()

    assert output == 'alpine\n'
