def test_stop(vm):
    with vm.run(wait_for_ssh=30):
        vm.stop()
        assert not vm.is_running


def test_kill(vm):
    with vm.run(wait_for_ssh=30):
        assert vm.qmp_path.exists()
        vm.kill(wait=True)
        assert not vm.qmp_path.exists()


def test_destroy(vm):
    assert vm.path.exists()
    vm.destroy()
    assert not vm.path.exists()


def test_destroy_running_image(vm):
    with vm.run(wait_for_ssh=30):
        assert vm.qmp_path.exists()
        assert vm.path.exists()
        vm.destroy()
        assert not vm.qmp_path.exists()
        assert not vm.path.exists()
