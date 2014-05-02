__author__ = 'achmed'

import gevent
import signal

import logging
logger = logging.getLogger()

class BaseService(object):
    def __init__(self):
        logger.debug('constructed base service')

    def machine_id(self):
        return self.machineid

    # override in subclasses for status that inspects
    def service_status(self):
        '''
        get the status of this service
        '''
        return 'OK'

    # hacky alarm-based terminate
    def terminate(self):
        '''
        stops the service
        '''

        def do_term(signum, frame):
            gevent.sleep(0)
            import sys
            sys.exit(0)

        self._stop()

        signal.signal(signal.SIGALRM, do_term)
        signal.alarm(2)

        return True

    # hook for the work of stopping the service (stop threads)
    def _stop(self):
        pass