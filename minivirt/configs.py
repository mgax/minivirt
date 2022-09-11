import json
from functools import cached_property


class Config:
    def __init__(self, path):
        self.path = path

    @cached_property
    def content(self):
        try:
            with self.path.open() as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('w') as f:
            json.dump(self.content, f, indent=2)

        self.__dict__.pop('content', None)

    def __getitem__(self, key):
        return self.content[key]

    def __setitem__(self, key, value):
        self.content[key] = value

    def update(self, *args, **kwargs):
        self.content.update(*args, **kwargs)

    def get(self, key, default=None):
        return self.content.get(key, default)

    def setdefault(self, key, default):
        return self.content.setdefault(key, default)
