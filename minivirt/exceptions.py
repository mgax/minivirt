class VmExists(RuntimeError):
    pass


class VmIsRunning(RuntimeError):
    pass


class ImageNotFound(Exception):
    pass


class WaitTimeout(RuntimeError):
    pass
