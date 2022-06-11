import subprocess
from pathlib import Path


def test_connect_with_ssh(vm):
    with vm.run(wait_for_ssh=True):
        ssh_config = Path(__file__).parent / 'ssh_config'
        out = subprocess.check_output(
            ['ssh', '-F', ssh_config, 'foo.minivirt', 'hostname']
        )
    assert out.strip() == b'alpine'
