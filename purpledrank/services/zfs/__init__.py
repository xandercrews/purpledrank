__author__ = 'achmed'

'''
data sources are responsible for discretizing their own data

responses should be multipart messages which may contain more than one object
or just one, but in a sequence all the same.  data must be returned in this format:
[
  {                             # the envelope
    "id": <id>,
    "agentid": <agentid">,      # the agent which collected the data (and the key for the config)
    "sourceid": <sourceid>,     # the object which the data pertains to (i.e. the host or device and not the proxy)
    "timestamp": <timestamp>,
    "_": {                      # anything you want, the actual data
      ...
    }
  },
  {                             # another one
    ...
  }
]
'''


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
from ...backends.comstar import STMFDataInterface, ITAdmDataInterface

from ...envelopeutil import make_envelope_foreach
from ...timeutil import utctimestamp

import logging
logger = logging.getLogger(__name__)

class ZFSService(BaseService):
    def __init__(self):
        BaseService.__init__(self)
        self.sourceid = self.config['sourceid']

    def get_zpool_status(self, pool=None):
        '''
        returns a dict structure of all zfs zpools, or a specific pool if specified
        '''

        timestamp = utctimestamp()
        zs = ZFSDataInterface.zpool_status(pool)

        return make_envelope_foreach(zs, 'zpool_status', self.sourceid, timestamp)

    def get_zpool_properties(self, pool=None):
        '''
        returns the properties of all zfs pools, or a specific pool if specified
        '''
        return ZFSDataInterface.zpool_properties(pool)

    def get_zfs_volume_properties(self):
        '''
        get the properties of all zfs volumes
        '''
        return ZFSDataInterface.zfs_volume_properties()

    def get_stmf_targets(self):
        '''
        get all stmf targets
        '''
        return STMFDataInterface.stmf_list_targets()

    def get_itadm_target_properties(self):
        '''
        get all itadm properties
        '''
        return ITAdmDataInterface.itadm_target_properties()

    # @zerorpc.stream
    # def rc_test(self):
    #     logger.info('started rc test')
    #     q = Queue.Queue(maxsize=10)     # bound the size of the queue to detect when it's not keeping up
    #     stopevent = threading.Event()
    #
    #     def strobe():
    #         try:
    #             q.put((time.time(), 1), timeout=10)
    #         except Queue.Full:
    #             stopevent.set()
    #
    #     pt = PeriodicTimer(1, strobe)
    #
    #     g = gevent.spawn(pt.loop, stopevent)
    #
    #     while True:
    #         yield q.get()
    #
    #     g.join()

