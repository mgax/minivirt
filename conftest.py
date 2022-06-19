import pytest

from minivirt import qemu


def pytest_addoption(parser):
    parser.addoption('--runslow', action='store_true', help='Run slow tests')


def pytest_configure(config):
    config.addinivalue_line('markers', 'slow: mark test as slow to run')
    config.addinivalue_line('markers', 'arch: run only on these architectures')


def pytest_collection_modifyitems(config, items):
    for item in items:
        if 'slow' in item.keywords:
            if not config.getoption('--runslow'):
                item.add_marker(
                    pytest.mark.skip(reason='need --runslow option to run')
                )

        if 'arch' in item.keywords:
            supported = list(item.keywords['arch'].args)
            if qemu.arch not in supported:
                item.add_marker(
                    pytest.mark.skip(reason=f'only runs on {supported}')
                )
