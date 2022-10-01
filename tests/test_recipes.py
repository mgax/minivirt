from pathlib import Path

import pytest

from minivirt.build import build

recipes = (Path(__file__).resolve().parent.parent / 'recipes')


@pytest.mark.slow
@pytest.mark.parametrize('path', list(recipes.glob('*.yaml')))
def test_build_recipe(db, path):
    if path.name == 'ubuntu-22.04.yaml':
        pytest.skip(f'Recipe {path.name} is broken')
    image = build(db, path)
    assert image is not None
