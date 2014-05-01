__author__ = 'achmed'

import subprocess

import gevent
import gevent.monkey

import threading

gevent.monkey.patch_socket()
gevent.monkey.patch_time()

from ...timer import PeriodicTimer
import time

import Queue

from ..baseservice import BaseService
import zerorpc
from gevent import sleep

import grammars.zpoolstatus

import sys

if sys.platform.startswith('sunos'):
    ZPOOL_CMD = '/usr/sbin/zpool'
else:
    ZPOOL_CMD = '/usr/bin/zpool'

import logging
logger = logging.getLogger()

class ZFSService(BaseService):
    @zerorpc.stream
    def rc_test(self):
        logger.info('started rc test')
        q = Queue.Queue(maxsize=10)     # bound the size of the queue to detect when it's not keeping up
        stopevent = threading.Event()

        def strobe():
            try:
                q.put((time.time(), 1), timeout=10)
            except Queue.Full:
                stopevent.set()

        pt = PeriodicTimer(1, strobe)

        g = gevent.spawn(pt.loop, stopevent)

        while True:
            yield q.get()

        g.join()

    def get_zpool_status(self):
        p = subprocess.Popen([ZPOOL_CMD, 'status',], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
        out, err = p.communicate()
        if p.returncode != 0:
            raise Exception('zpool status command failed: %s' % err)

        parser = grammars.zpoolstatus.LanguageOfZpoolStatuses.parser()
        r = parser.parse_string(out, eof=True)

        return r is not None
