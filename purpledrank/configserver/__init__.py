__author__ = 'achmed'

import os
import yaml

from ..errors import ConfigNotFoundException

from ..log import init_logger
init_logger()

import logging
logger = logging.getLogger(__name__)

def search_for_config():
    # TODO make something other than a static location
    return os.path.join(os.path.abspath(os.getcwd()), 'conf/config.yaml')

def search_for_log_config():
    return os.path.join(os.path.abspath(os.getcwd()), 'conf/logging.yaml')

class ConfigServer(object):
    def __init__(self):
        pass

    def refreshConfig(self):
        configpath = search_for_config()
        with open(configpath, 'r') as fh:
            self.config = yaml.safe_load(fh)

        logconfigpath = search_for_log_config()
        with open(logconfigpath, 'r') as fh:
            self.logconfig = yaml.safe_load(fh)

    def get_config(self, name):
        self.refreshConfig()

        logger.info('client \'%s\' requested config' % name)
        c = self.config.get(name, None)
        if c is None:
            raise ConfigNotFoundException()
        return c

    def get_logging_config(self):
        self.refreshConfig()

        return self.logconfig
