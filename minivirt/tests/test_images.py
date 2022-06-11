import tempfile
import shutil

from minivirt.vms import VM


def test_save_restore_run(db, ssh):
    VM.open(db, 'foo').destroy()
    image_path = db.image_path('newly-loaded-image')
    if image_path.exists():
        shutil.rmtree(image_path)

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
        shutil.rmtree(image_path)
