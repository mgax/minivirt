def test_kill(vm):
    with vm.run(wait_for_ssh=True):
        assert vm.qmp_path.exists()
        vm.kill(wait=True)
        assert not vm.qmp_path.exists()


def test_destroy(vm):
    assert vm.path.exists()
    vm.destroy()
    assert not vm.path.exists()


def test_destroy_running_image(vm):
    with vm.run(wait_for_ssh=True):
        assert vm.qmp_path.exists()
        assert vm.path.exists()
        vm.destroy()
        assert not vm.qmp_path.exists()
        assert not vm.path.exists()
