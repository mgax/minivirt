def test_set_memory_size(vm, ssh):
    vm._write_config(dict(vm.config, memory=200))
    with vm.run(wait_for_ssh=30):
        out = ssh(vm, 'grep MemTotal /proc/meminfo')
        memory_mb = int(out.split()[1]) / 2**10
        assert 150 < memory_mb < 200
