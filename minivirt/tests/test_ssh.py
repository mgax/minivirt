def test_connect_with_ssh(vm, ssh):
    with vm.run(wait_for_ssh=30):
        out = ssh(vm, 'hostname')
    assert out.strip() == b'alpine'
