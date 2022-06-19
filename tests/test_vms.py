import pytest

from minivirt.exceptions import VmIsRunning
from minivirt.utils import waitfor


def test_start_started_vm_raises_exception(vm):
    with vm.run():
        waitfor(lambda: vm.is_running)
        with pytest.raises(VmIsRunning):
            vm.start()
