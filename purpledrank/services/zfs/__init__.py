__author__ = 'achmed'

import subprocess

import gevent

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
        q = Queue.Queue()

        def strobe():
            logger.info('strobe called')
            print 'strobe called'
            q.put((time.time(), 1))

        pt = PeriodicTimer(1, strobe)

        logger.info('spawning gevent')
        print 'spawning gevent?'
        g = gevent.spawn(pt.loop)

        while True:
            logger.info('waiting on queue')
            print 'waiting on queue'
            yield q.get()

        g.join()
