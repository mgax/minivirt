import random
import socket

from minivirt.vms import PortForward, VM


def test_connect_with_ssh(vm):
    with vm.run(wait_for_ssh=30):
        out = vm.ssh('hostname', capture=True)
    assert out.strip() == b'alpine'


def test_tcp_port(db):
    db.get_vm('foo').destroy()
    base = db.get_image('base')
    host_port = random.randrange(20000, 32000)
    ports = [PortForward(host_port, 22)]
    vm = VM.create(db, 'foo', image=base, memory=512, ports=ports)
    try:
        with vm.run(wait_for_ssh=30):
            sock = socket.create_connection(('localhost', host_port))
            assert sock.recv(3) == b'SSH'
    finally:
        vm.destroy()
