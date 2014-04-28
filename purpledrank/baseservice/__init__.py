__author__ = 'achmed'

import zerorpc
import zerorpc.exceptions

from ..errors import ConfigNotFoundException, ServiceNotConfiguredException

import machineid

import logging
logger = logging.getLogger()
import logging.config

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

class BaseService(object):
    pass

class DiscoveryService(BaseService):
    def __init__(self):
        logger.info('discovery service built')

    def terminate(self):
        import sys
        sys.exit(0)

    def logsomethin(self):
        logger.critical('crit')
        logger.error('err')
        logger.warn('warn')
        logger.info('info')
        logger.debug('debug')

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
            pkg, cls = servicepath.rsplit('.', 1)
            serviceclass = RemoteServiceConfigMetaclass.loader(pkg, cls)
            logger.info('post load %s, %s' % (repr(serviceclass), serviceclass.__class__))
            # bases = [ serviceclass ] + list(bases)
            bases = [ DiscoveryService ] + list(bases)

            logger.info('constructed with class %s' % servicepath)
        except zerorpc.exceptions.RemoteError, e:
            if e.name == 'ConfigNotFoundException':
                bases = [ DiscoveryService ] + list(bases)
                logger.info('could not determine remote class, built with discovery class')
            else:
                raise

        logger.debug('bases %s' % ','.join(map(repr, bases)))
        # logger.debug('base types %s' % ','.join(map(lambda b: b.__class__, bases)))
        logger.debug('base types %s' % ','.join(map(lambda b: str(b.__class__), bases)))
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
        return '127.0.0.1', 9191

    @staticmethod
    def get_config(ID):
        c = zerorpc.Client('tcp://%s:%d' % RemoteServiceConfigMetaclass.get_config_connect_params())
        config = c.get_config(ID)
        c.close()

        return config

class MagicService(object):
    __metaclass__ = RemoteServiceConfigMetaclass

    # def __init__(self):
    #     super(MagicService, self).__init__()
