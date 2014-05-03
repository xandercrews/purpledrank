__author__ = 'achmed'

import redis
from ...redisutil import scan_iter, make_prefix, add_prefix

from ...purpleutil import dictequal

from ..baseservice import BaseService

import sys

from ...timer import PeriodicTimer

import threading
import zerorpc

import logging
logger = logging.getLogger(__name__)

import functools

# import msgpack as endecoder
import json as endecoder

class RedisCollectionThread(threading.Thread):
    def __init__(self, sourcename, host, port, interval, method, args, rconn):
        '''
        :type rconn: redis.StrictRedis
        '''
        threading.Thread.__init__(self)
        self.sourcename = sourcename
        self.host = host
        self.port = port
        self.method = method
        self.interval = interval
        try:
            self.client = zerorpc.Client('tcp://%s:%d' % (self.host, self.port))
            self.agentid = self.client.agent_id()
        except Exception, e:
            raise Exception('couldn\'t create client connection to source: %s' % str(e)), None, sys.exc_info()[2]
        self.collection_method = functools.partial(self.client.__getattr__(self.method), *args)
        self.rconn = rconn

        self.redis_key = make_prefix(self.sourcename, self.agentid)
        self.redis_pub_key = make_prefix(self.sourcename)

    def run(self):
        self.stopevent = threading.Event()
        def cb():
            data = self.collection_method()
            # TODO multi writer
            logger.debug('from agent %s collected %s' % (self.agentid, str(data)))
            old_data = self.rconn.get(self.redis_key)
            if old_data is not None:
                old_data = endecoder.loads(old_data)
            if old_data is None or not dictequal(data, old_data):
                self.rconn.set(self.redis_key, endecoder.dumps(data))
                self.rconn.publish(self.redis_pub_key, endecoder.dumps(dict(key=self.redis_key)))
                logger.info('updated and published record %s' % self.redis_key)
        self.pt = PeriodicTimer(self.interval, cb, immediate=True)
        self.pt.loop(self.stopevent)

    def stop(self):
        # TODO finish
        self.stopevent.set()
        logger.info('waiting for collector to stop')
        self.join()


class RedisCollectorService(BaseService):
    def __init__(self):
        BaseService.__init__(self)
        self._redis_conn()
        self._start_workers()

    def _redis_conn(self):
        host = self.config['redis']['host']
        port = int(self.config['redis']['port'])
        self.redis_conn = redis.StrictRedis(host=host, port=port, db=0)

    def _start_workers(self):
        self.workers = []
        for source in self.config['sources']:
            name = source['name']
            host, port = source['host'], source['port']
            method = source['method']
            interval = source['interval']
            args = source['args']
            t = RedisCollectionThread(name, host, port, interval, method, args, self.redis_conn)
            self.workers.append(t)

        for t in self.workers:
            t.start()

    def worker_stuff(self):
        return str(self.workers)
