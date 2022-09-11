from pathlib import Path

import pytest

from minivirt.build import build

recipes = (Path(__file__).resolve().parent.parent / 'recipes')


@pytest.mark.slow
@pytest.mark.parametrize('path', list(recipes.glob('*.yaml')))
def test_build_recipe(db, path):
    image = build(db, path)
    assert image is not None
