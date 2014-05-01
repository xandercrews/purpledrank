__author__ = 'achmed'

import subprocess

import gevent

from ...timer import PeriodicTimer
import time

import Queue

from ..baseservice import BaseService
import zerorpc
from gevent import sleep

class ZFSService(BaseService):
    def hello(self):
        return 'hello'

    @zerorpc.stream
    def rc_test(self):
        q = Queue.Queue()

        def strobe():
            q.put((time.time(), 1))

        pt = PeriodicTimer(1, strobe)

        g = gevent.spawn(pt.loop)

        while True:
            yield q.get()

        g.join()
