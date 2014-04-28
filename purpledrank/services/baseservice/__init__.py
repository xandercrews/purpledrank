__author__ = 'achmed'

import logging
logger = logging.getLogger()

class BaseService(object):
    def __init__(self):
        logger.debug('constructed base service')

    def service_status(self):
        return 'OK'
