__author__ = 'achmed'

'''
data sources are responsible for discretizing their own data

responses should be multipart and may contain one or more objects (or 0 i guess)
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
        timestamp = utctimestamp()
        zp = ZFSDataInterface.zpool_properties(pool)

        return make_envelope_foreach(zp, 'zpool_properties', self.sourceid, timestamp)

    def get_zvol_properties(self):
        '''
        get the properties of all zfs volumes
        '''
        timestamp = utctimestamp()
        zp = ZFSDataInterface.zfs_volume_properties()

        return make_envelope_foreach(zp, 'zvol_properties', self.sourceid, timestamp)

    def get_stmf_targets(self):
        '''
        get all stmf targets
        '''
        timestamp = utctimestamp()
        lt = STMFDataInterface.stmf_list_targets()

        if 'hgs' in lt:
            hgs = make_envelope_foreach(lt['hgs'], 'stmf_hgs', self.sourceid, timestamp)
        else:
            hgs = []

        if 'luns' in lt:
            luns = make_envelope_foreach(lt['luns'], 'stmf_luns', self.sourceid, timestamp)
        else:
            luns = []

        if 'tgs' in lt:
            tgs = make_envelope_foreach(lt['tgs'], 'stmf_tgs', self.sourceid, timestamp)
        else:
            tgs = []

        return hgs + luns + tgs

    def get_itadm_target_properties(self):
        '''
        get all itadm properties
        '''
        timestamp = utctimestamp()
        tp = ITAdmDataInterface.itadm_target_properties()

        if 'hgs' in tp:
            targets = make_envelope_foreach(tp['targets'], 'itadm_targets', self.sourceid, timestamp)
        else:
            targets = []

        if 'tgps' in tp:
            tpgs = make_envelope_foreach(tp['tpgs'], 'itadm_tpgs', self.sourceid, timestamp)
        else:
            tpgs = []

        return targets + tpgs

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

