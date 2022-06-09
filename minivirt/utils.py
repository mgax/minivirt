import logging
from time import time, sleep

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def waitfor(condition, timeout=10, poll_interval=0.1):
    expires = time() + timeout
    while time() < expires:
        logger.debug('Polling for %r ...', condition)
        rv = condition()
        if rv:
            logger.debug('Polling for %r successful: %r.', condition, rv)
            return rv
        sleep(poll_interval)

    raise RuntimeError('Timeout expired')
