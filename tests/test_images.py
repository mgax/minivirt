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
            db, 'foo', image=db.get_image('newly-loaded-image'), memory=512
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

    vm.commit().tag('newly-committed-image')
    db.remove_image('base')

    try:
        bar = VM.create(
            db, 'bar', image=db.get_image('newly-committed-image'), memory=512
        )
        with bar.run(wait_for_ssh=60):
            out = bar.ssh('ls', capture=True)
        assert out.strip() == b'marker-file'

    finally:
        db.get_vm('bar').destroy()
        db.remove_image('newly-committed-image')


def test_commit_overwrite_tag(db, vm):
    vm.commit().tag('thing')
    thing_id = db.get_image('thing').name
    with vm.run(wait_for_ssh=30):
        pass
    vm.commit().tag('thing')
    assert db.get_image('thing').name != thing_id


def test_checksum(db):
    with db.create_image() as creator:
        with (creator.path / 'foo').open('wb') as f:
            f.write(b'Hello,')
        with (creator.path / 'bar').open('wb') as f:
            f.write(b'World!')
    # bar:514b6bb7c846ecfb8d2d29ef0b5c79b63e6ae838f123da936fe827fda654276c
    # foo:dafe7694460f4e37b708f5134f2f7f759cb997f9cb612d6ca566dd6e6a34353f
    assert creator.image.name == (
        '8492b89d0572b9dd3ee9597aa308c0887c1d26844dddbdd1c92408307f677887'
    )
