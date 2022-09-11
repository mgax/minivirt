import hashlib
import subprocess
import tempfile
from pathlib import Path


class Cache:
    def __init__(self, path):
        self.path = path

    def key(self, url):
        return hashlib.sha256(url.encode('utf8')).hexdigest()

    def get(self, url):
        key = self.key(url)
        path = self.path / key
        if path.exists():
            return path

        with tempfile.TemporaryDirectory(dir=self.path) as tmp:
            tmp_path = Path(tmp) / key
            subprocess.check_call(['curl', '-L', url, '-o', tmp_path])
            tmp_path.rename(path)

        return path
