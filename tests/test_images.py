import tempfile

from minivirt.vms import VM


def test_save_restore_run(db):
    db.get_vm('foo').destroy()
    db.remove_image('newly-loaded-image')

    with tempfile.TemporaryFile() as f:
        db.save('base', stdout=f)
        f.seek(0)
        db.load('newly-loaded-image', stdin=f)

    try:
        vm = VM.create(
            db, 'foo', db.get_image('newly-loaded-image'), memory=512
        )
        with vm.run(wait_for_ssh=30):
            out = vm.ssh('hostname', capture=True)
        assert out.strip() == b'alpine'

    finally:
        db.get_vm('foo').destroy()
        db.remove_image('newly-loaded-image')


def test_commit_run(db, vm):
    db.get_vm('bar').destroy()
    db.remove_image('newly-committed-image')

    with vm.run(wait_for_ssh=30):
        vm.ssh('touch marker-file && poweroff')

    vm.commit('newly-committed-image')
    db.remove_image('base')

    try:
        bar = VM.create(
            db, 'bar', db.get_image('newly-committed-image'), memory=512
        )
        with bar.run(wait_for_ssh=30):
            out = bar.ssh('ls', capture=True)
        assert out.strip() == b'marker-file'

    finally:
        db.get_vm('bar').destroy()
        db.remove_image('newly-committed-image')