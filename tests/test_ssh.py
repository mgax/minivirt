def test_connect_with_ssh(vm):
    with vm.run(wait_for_ssh=30):
        out = vm.ssh('hostname', capture=True)
    assert out.strip() == b'alpine'
