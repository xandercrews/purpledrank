__author__ = 'achmed'

import zerorpc

class RemoteServiceConfigMixin(object):
    def __init__(self, configname, confighost, configport, **kwargs):
        self.configname = configname
        self.confighost = confighost
        self.configport = configport
        self.updateConfig()

    def updateConfig(self):
        c = zerorpc.Client('tcp://%s:%d' % (self.confighost, self.configport,))
        self.config = c.get_config(self.configname)
        c.close()

class BaseService(RemoteServiceConfigMixin):
    def __init__(self, **kwargs):
        RemoteServiceConfigMixin.__init__(**kwargs)
