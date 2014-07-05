__author__ = 'achmed'

import zerorpc
import time
import random
import gevent.monkey

gevent.monkey.patch_time()

class SomeService(object):
    def hello(self, name):
        return 'hi there %s' % name

    @zerorpc.stream
    def stream(self, duration=60):
        self.stop = False
        for i in xrange(duration):
            time.sleep(1)
            yield time.time(), random.random()
            if self.stop:
                yield 'stopping'
                break

    def stop(self):
        self.stop = True

    @zerorpc.stream
    def stream_forever(self):
        self.stop = False
        while True:
            if self.stop:
                yield 'stopping'
                break
            yield time.time()
            time.sleep(1)

c = zerorpc.Server(SomeService())
c.bind('tcp://127.0.0.1:9292')
c.run()
