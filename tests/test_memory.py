def test_set_memory_size(vm):
    vm.config['memory'] = 200
    vm.config.save()
    with vm.run(wait_for_ssh=30):
        out = vm.ssh('grep MemTotal /proc/meminfo', capture=True)
        memory_mb = int(out.split()[1]) / 2**10
        assert 150 < memory_mb < 200
