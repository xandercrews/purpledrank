__author__ = 'achmed'

from ..baseservice import BaseService
import zerorpc
import gevent

class TestService(BaseService):
    @zerorpc.stream
    def stream_forever(self):
        while True:
            gevent.sleep(1)
            yield 1

    def return_true(self):
        return True
