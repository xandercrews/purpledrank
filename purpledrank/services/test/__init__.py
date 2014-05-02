__author__ = 'achmed'

from ..baseservice import BaseService
import zerorpc
import gevent

import threading

import logging
logger = logging.getLogger()

class TestService(BaseService):
    @zerorpc.stream
    def stream_forever(self):
        while True:
            gevent.sleep(1)
            yield 1

    def return_true(self):
        return True

class WorkerThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.shutdown = threading.Event()

    def run(self):
        while True:
            gevent.sleep(1)
            if self.shutdown.is_set():
                break
            logger.info('worker thread still here')

    def stop(self):
        self.shutdown.set()
        logger.info('waiting for thread to stop')
        self.join()

class ThreadTestService(BaseService):
    def __init__(self, *args, **kwargs):
        BaseService.__init__(self, *args, **kwargs)
        self.wt = WorkerThread()
        self.wt.start()

    def threadstuff(self):
        logger.info(repr(self.wt))

    def _stop(self):
        self.wt.stop()
