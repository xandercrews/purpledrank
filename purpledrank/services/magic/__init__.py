__author__ = 'achmed'

import gevent
import gevent.monkey
gevent.monkey.patch_time()

import os
import sys

import machineid

from ..baseservice import BaseService

from ...errors import ServiceNotConfiguredException

import zerorpc
import zerorpc.exceptions

import logging
logger = logging.getLogger(__name__)
import logging.config

def reset_logging():
    global logger
    for handler in logging.root.handlers[:]:
        print handler
        logging.root.removeHandler(handler)
    logger = logging.getLogger()


class DiscoveryService(BaseService):
    def __init__(self):
        super(DiscoveryService, self).__init__()
        logger.info('constructed discovery service')

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
            dct['machineid'] = ID

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
        print 'getting log config'
        config_params = RemoteServiceConfigMetaclass.get_config_connect_params()
        assert len(config_params) == 2, 'there should be a host and port in connect params for config server'
        c = zerorpc.Client('tcp://%s:%s' % config_params)
        try:
            l = c.get_logging_config()
            # reset_logging()    # unnecessary
            logging.config.dictConfig(l)
            logger.info('logger configured from remote')
        except Exception, e:
            error = 'couldn\'t load log config- %s' % str(e)
            logger.warn(error)
            print >>sys.stderr, error
        c.close()

    @staticmethod
    def loader(package, cls):
        logger.info('attempt load')
        return __import__(package, fromlist=[cls])

    @staticmethod
    def get_config_connect_params():
        # TODO get config server host and port
        port = os.environ.get('PURPLE_CONFIG_PORT', '9191')
        try:
            assert str(int(port)) == port
        except (TypeError, AssertionError):
            raise Exception('port needs to be a number')
        if not 1 <= int(port) <= 65535:
            raise Exception('port needs to be between 1-65535')
        return os.environ.get('PURPLE_CONFIG_HOST', '127.0.0.1'), port

    @staticmethod
    def get_config(ID):
        config_params = RemoteServiceConfigMetaclass.get_config_connect_params()
        assert len(config_params) == 2, 'there should be a host and port in connect params for config server'
        c = zerorpc.Client('tcp://%s:%s' % config_params)
        config = c.get_config(ID)
        c.close()

        return config

class MagicService(object):
    __metaclass__ = RemoteServiceConfigMetaclass
