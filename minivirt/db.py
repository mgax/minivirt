from pathlib import Path
import subprocess


class DB:
    def __init__(self):
        self.path = Path.home() / '.cache' / 'minivirt'
        self.path.mkdir(parents=True, exist_ok=True)

    def image_path(self, filename):
        return self.path / filename

    def vm_path(self, name):
        return self.path / name

    def download_image(self, url, filename):
        subprocess.check_call(
            ['curl', '-L', url, '-o', self.image_path(filename)]
        )
