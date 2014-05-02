__author__ = 'achmed'

from ... import backends

import subprocess
import threading

import gevent
import gevent.monkey

gevent.monkey.patch_socket()
gevent.monkey.patch_time()

from ...timer import PeriodicTimer
import time

import Queue

from ..baseservice import BaseService
import zerorpc

from ...backends.zfs import ZFSDataInterface

import logging
logger = logging.getLogger()

class ZFSService(BaseService):
    def get_zpool_status(self, pool=None):
        return ZFSDataInterface.zpool_status(pool)

    def get_zpool_properties(self, pool=None):
        return ZFSDataInterface.zpool_properties(pool)

    def get_zfs_volume_properties(self):
        return ZFSDataInterface.zfs_volume_properties()

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

