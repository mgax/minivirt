import tempfile

from minivirt.vms import VM


def test_save_restore_run(db, ssh):
    VM.open(db, 'foo').destroy()
    db.remove_image('newly-loaded-image')

    with tempfile.TemporaryFile() as f:
        db.save('base', stdout=f)
        f.seek(0)
        db.load('newly-loaded-image', stdin=f)

    try:
        vm = VM.create(db, 'foo', db.get_image('newly-loaded-image'))
        with vm.run(wait_for_ssh=True):
            out = ssh(vm, 'hostname')
        assert out.strip() == b'alpine'

    finally:
        VM.open(db, 'foo').destroy()
        db.remove_image('newly-loaded-image')


def test_commit_run(db, vm, ssh):
    VM.open(db, 'bar').destroy()
    db.remove_image('newly-committed-image')

    with vm.run(wait_for_ssh=True):
        ssh(vm, 'touch marker-file && poweroff')

    vm.commit('newly-committed-image')
    db.remove_image('base')

    try:
        bar = VM.create(db, 'bar', db.get_image('newly-committed-image'))
        with bar.run(wait_for_ssh=True):
            out = ssh(bar, 'ls')
        assert out.strip() == b'marker-file'

    finally:
        VM.open(db, 'bar').destroy()
        db.remove_image('newly-committed-image')
