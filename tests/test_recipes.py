from pathlib import Path

import pytest

from minivirt.build import build

recipes = (Path(__file__).resolve().parent.parent / 'recipes')


@pytest.mark.slow
@pytest.mark.parametrize('name', ['alpine-3.16', 'ubuntu-22.04'])
def test_build_recipe(db, name):
    image = build(db, recipes / f'{name}.yaml')
    assert image is not None
