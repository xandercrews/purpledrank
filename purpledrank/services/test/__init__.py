__author__ = 'achmed'

from ..baseservice import BaseService
import gevent

class TestService(BaseService):
    def stream_forever(self):
        while True:
            gevent.sleep(1)
            yield 1

    def return_true(self):
        return True
