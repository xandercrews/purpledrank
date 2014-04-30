__author__ = 'achmed'

import gevent
import gevent.monkey
gevent.monkey.patch_time()

import os

import machineid

from ..baseservice import BaseService

from ...errors import ServiceNotConfiguredException

import zerorpc
import zerorpc.exceptions

import logging
logger = logging.getLogger()
import logging.config

import sched
import time

def reset_logging():
    global logger
    for handler in logging.root.handlers[:]:
        print handler
        logging.root.removeHandler(handler)
    logger = logging.getLogger()


# class RemoteServiceConfigMixin(object):
#     def __init__(self, configname, confighost, configport, **kwargs):
#         self.configname = configname
#         self.confighost = confighost
#         self.configport = configport
#         self.updateConfig()
#         self.updateLoggingConfig()
#
#     def updateConfig(self):
#         c = zerorpc.Client('tcp://%s:%d' % (self.confighost, self.configport,))
#         self.config = c.get_config(self.configname)
#         c.close()
#
#     def updateLoggingConfig(self):
#         c = zerorpc.Client('tcp://%s:%d' % (self.confighost, self.configport,))
#         try:
#             l = c.get_logging_config()
#             logging.config.dictConfig(l)
#         except Exception, e:
#             logger.warn('couldn\'t load log config- %s' % str(e))
#         c.close()
#
# class BaseService(RemoteServiceConfigMixin):
#     def __init__(self, **kwargs):
#         RemoteServiceConfigMixin.__init__(**kwargs)
#

class DiscoveryService(BaseService):
    def __init__(self):
        super(DiscoveryService, self).__init__()
        logger.info('constructed discovery service')

    def terminate(self):
        # hacky

        def do_term(self):
            gevent.sleep(0)
            import sys
            sys.exit(0)

        s = sched.scheduler(time.time, gevent.sleep)
        s.enter(2, 0, do_term, None)
        s.run()

        return True

class RemoteServiceConfigMetaclass(type):
    def __new__(cls, name, bases, dct):
        '''
        :type bases: list
        '''
        RemoteServiceConfigMetaclass.updateLoggingConfig()

        # get the remote config
        ID = machineid.get_machine_id()
        try:
            config = RemoteServiceConfigMetaclass.get_config(ID)
            dct['config'] = config

            if 'service' not in config:
                raise ServiceNotConfiguredException()

            servicepath = config['service']
            if '.' in servicepath:
                modulepath, objname = servicepath.rsplit('.', 1)
                module = __import__(modulepath, fromlist=[objname])
                serviceclass = getattr(module, objname)
            else:
                serviceclass = __import__(servicepath)
            logger.info('post load %s, %s' % (repr(serviceclass), serviceclass.__class__))
            bases = [ serviceclass ] + list(bases)

            logger.info('constructed with class %s' % servicepath)
        except zerorpc.exceptions.RemoteError, e:
            if e.name == 'ConfigNotFoundException':
                bases = [ DiscoveryService ] + list(bases)
                logger.info('could not determine remote class, built with discovery class')
            else:
                raise

        logger.debug('bases %s' % ','.join(map(repr, bases)))
        return type.__new__(cls, name, tuple(bases), dct)

    @staticmethod
    def updateLoggingConfig():
        global logger
        c = zerorpc.Client('tcp://%s:%d' % RemoteServiceConfigMetaclass.get_config_connect_params())
        try:
            l = c.get_logging_config()
            # reset_logging()    # unnecessary
            logging.config.dictConfig(l)
            logger.info('logger configured from remote')
        except Exception, e:
            logger.warn('couldn\'t load log config- %s' % str(e))
        c.close()

    @staticmethod
    def loader(package, cls):
        logger.info('attempt load')
        return __import__(package, fromlist=[cls])

    @staticmethod
    def get_config_connect_params():
        # TODO get config server host and port
        return os.environ.get('PURPLE_CONFIG_HOST', '127.0.0.1'), os.environ.get('PURPLE_CONFIG_PORT', 9191)

    @staticmethod
    def get_config(ID):
        config_params = RemoteServiceConfigMetaclass.get_config_connect_params()
        assert len(config_params) == 2, 'there should be a host and port in connect params for config server'
        c = zerorpc.Client('tcp://%s:%d' % config_params)
        config = c.get_config(ID)
        c.close()

        return config


        # def __init__(self):
        #     super(MagicService, self).__init__()

class MagicService(object):
    __metaclass__ = RemoteServiceConfigMetaclass
