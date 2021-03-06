import shutil


def test_ok_image_and_vm(db, vm):
    assert not db.fsck().errors


def test_invalid_image_checksum(db):
    (db.get_image('base').path / 'intruder').touch()
    result = db.fsck()
    assert len(result.errors) == 1
    assert 'invalid checksum' in result.errors[0]


def test_missing_image(db, vm):
    shutil.rmtree(db.get_image('base').path)
    db.get_tag('base').delete()
    result = db.fsck()
    assert len(result.errors) == 1
    assert 'missing image' in result.errors[0]


def test_dangling_tag(db):
    shutil.rmtree(db.get_image('base').path)
    result = db.fsck()
    assert len(result.errors) == 1
    assert 'target image does not exist' in result.errors[0]
