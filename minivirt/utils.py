import logging
import select
import socket
from time import sleep, time

logger = logging.getLogger(__name__)


class WaitTimeout(RuntimeError):
    pass


def waitfor(condition, help=None, timeout=10, poll_interval=0.1):
    if not help:
        help = (condition.__doc__ or repr(condition)).strip()
    expires = time() + timeout
    while time() < expires:
        logger.debug('Polling for %s ...', help)
        rv = condition()
        if rv:
            logger.debug('Polling for %s successful: %r.', help, rv)
            return rv
        sleep(poll_interval)

    raise WaitTimeout('Timeout expired')


def wait_for_ssh(port, timeout=10):
    def ssh_tcp():
        logger.debug('SSH: trying to connect to port %d ...', port)
        try:
            sock = socket.create_connection(('localhost', port))
        except OSError as e:
            logger.debug('SSH: got an OSError: %s', e)
            return False
        else:
            sock.setblocking(0)
            logger.debug('SSH: connected, reading 3 bytes ...')
            ready = select.select([sock], [], [], 0.1)
            logger.debug('SSH: ready: %r', ready)
            if not ready[0]:
                logger.debug('SSH: no data ready')
                return False
            buffer = sock.recv(3)
            logger.debug('SSH: received %s', buffer)
            if buffer == b'SSH':
                logger.debug('SSH: success!')
                return True

    waitfor(ssh_tcp, timeout=timeout)
