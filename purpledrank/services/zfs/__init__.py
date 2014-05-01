__author__ = 'achmed'

import subprocess

import gevent
import gevent.monkey

import threading

gevent.monkey.patch_all()

from ...timer import PeriodicTimer
import time

import Queue

from ..baseservice import BaseService
import zerorpc
from gevent import sleep

import logging
logger = logging.getLogger()

class ZFSService(BaseService):
    def hello(self):
        return 'hello'

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
