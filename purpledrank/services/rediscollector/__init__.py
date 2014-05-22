import collections

__author__ = 'achmed'

import redis
from ...redisutil import scan_iter, make_prefix, add_prefix

from ...purpleutil import dictequal

from ...errors import NotYetImplementedException

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

        self.redis_key_prefix = make_prefix(self.sourcename, self.agentid)
        self.redis_pub_key_prefix = make_prefix(self.sourcename)

    def run(self):
        self.stopevent = threading.Event()

        def periodic_cb():
            previous_keys = set(scan_iter(self.rconn, '%s\0*' % self.redis_key_prefix))

            data = self.collection_method()

            logger.debug('collected objects from agent %s method %s' % (self.agentid, self.method))

            process_keys = []

            for d in data:
                if not isinstance(d, collections.Mapping):
                    logger.error('object is not a mapping: %s' % str(d))
                    continue

                if 'id' not in d:
                    logger.error('id field not set in object: %s' % str(d))
                    continue

                if 'type' not in d:
                    logger.error('type field not set in object: %s' % str(d))
                    continue

                if 'sourceid' not in d:
                    logger.error('sourceid field not set in object: %s' % str(d))
                    continue

                if '_' not in d:
                    logger.error('data (_) field not set in object: %s' % str(d))
                    continue

                _id = d['id']
                _type = d['type']
                _sourceid = d['sourceid']

                logger.debug('processing object: %s' % str(d))

                redis_key = add_prefix(self.redis_key_prefix, _sourceid, _type, _id)
                redis_pub_key = add_prefix(self.redis_pub_key_prefix, _type)

                d['rkey'] = redis_key

                old_data = self.rconn.get(redis_key)

                update_record = False

                if old_data is None:
                    update_record = True
                    logger.info('creating and publishing record %s' % redis_key)
                else:
                    try:
                        old_data = endecoder.loads(old_data)

                        if not isinstance(old_data, collections.Mapping):
                            update_record = True
                            logger.error('previous data was not a mapping, overwriting')
                            logger.info('updating and publishing record %s' % redis_key)
                        elif '_' not in old_data:
                            update_record = True
                            logger.error('previous data did not include data (_) field, overwriting')
                            logger.info('updating and publishing record %s' % redis_key)
                        elif not dictequal(d['_'], old_data['_']):
                            update_record = True
                            logger.info('updating and publishing record %s' % redis_key)
                    except Exception, e:
                        logger.error('could not decode previous record, overwriting')
                        update_record = True

                if update_record:
                    r = endecoder.dumps(d)
                    self.rconn.set(redis_key, r)
                    self.rconn.publish(redis_pub_key, r)

                process_keys.append(redis_key)

            stale_keys = previous_keys - set(process_keys)
            logger.info('found %d stale keys, removing' % len(stale_keys))
            logger.debug('stale keys: [%s]' % ', '.join(stale_keys))

            for dkey in stale_keys:
                while True:
                    try:
                        with self.rconn.pipeline() as p:
                            p.watch(dkey)
                            v = p.get(dkey)
                            logger.debug(v)
                            if v is None:
                                break
                            v = endecoder.loads(v)

                            _id = v['id']
                            _type = v['type']
                            _sourceid = v['sourceid']

                            redis_key = add_prefix(self.redis_key_prefix, _sourceid, _type, _id)
                            redis_pub_key = add_prefix(self.redis_pub_key_prefix, _type)

                            p.multi()
                            v['rkey'] = redis_key
                            v['_'] = None
                            p.delete(dkey)
                            p.execute()

                        v = endecoder.dumps(v)
                        self.rconn.publish(redis_pub_key, v)
                        break
                    except redis.WatchError, e:
                        pass

        def streaming_cb():
            raise NotYetImplementedException()

        if self.interval is not None:
            self.pt = PeriodicTimer(self.interval, periodic_cb, immediate=True)
            self.pt.loop(self.stopevent)
        else:
            streaming_cb()

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
            interval = source.get('interval', None)
            args = source['args']
            t = RedisCollectionThread(name, host, port, interval, method, args, self.redis_conn)
            self.workers.append(t)

        for t in self.workers:
            # t.run()     # for debugging =/
            t.start()

    def worker_stuff(self):
        return str(self.workers)
