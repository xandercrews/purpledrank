__author__ = 'achmed'

from ..baseservice import BaseService

import sys

from ...timer import PeriodicTimer

import threading
import zerorpc

import logging
logger = logging.getLogger()

import functools

class RedisCollectionThread(threading.Thread):
    def __init__(self, host, port, interval, method, args):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.method = method
        self.interval = interval
        try:
            self.client = zerorpc.Client('tcp://%s:%d' % (self.host, self.port))
            self.machineid = self.client.machine_id()
        except Exception, e:
            raise Exception('couldn\'t create client connection to source: %s' % str(e)), None, sys.exc_info()[2]
        self.collection_method = functools.partial(self.client.__getattr__(self.method), *args)

    def run(self):
        stuff = self.collection_method()
        logger.info('from machine %s collected %s' % (self.machineid, str(stuff)))

class RedisCollectorService(BaseService):
    def __init__(self):
        BaseService.__init__(self)
        self._start_workers()

    def _start_workers(self):
        self.workers = []
        for source in self.config['sources']:
            host, port = source['host'], source['port']
            method = source['method']
            interval = source['interval']
            args = source['args']
            t = RedisCollectionThread(host, port, interval, method, args)
            self.workers.append(t)

        for t in self.workers:
            t.start()

    def worker_stuff(self):
        return str(self.workers)
