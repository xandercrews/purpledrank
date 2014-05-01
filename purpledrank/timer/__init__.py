__author__ = 'achmed'

from rt import monotonic_time
import gevent.monkey
import gevent
gevent.monkey.patch_time()

import logging
logger = logging.getLogger()
logging.basicConfig()
# logger.setLevel(logging.DEBUG)

class PeriodicTimer(object):
    def __init__(self, incr_time, cb, raw=False):
        self.raw = raw
        self.cb = cb
        self.incr_time = incr_time

        self.time_gen = self.get_next_time(monotonic_time(self.raw))
        self.cur_time, self.next_time = self.time_gen.next()

    def loop(self, stopevent):
        while True:
            delta = self.next_time - self.cur_time
            assert delta >= 0
            while self.cur_time < self.next_time:
                sleep_interval = self.next_time - self.cur_time
                logger.debug('sleeping for %.9fs' % sleep_interval)
                if stopevent.is_set():
                    break
                gevent.sleep(sleep_interval)
                self.cur_time = monotonic_time(self.raw)
            self.cur_time, self.next_time = self.time_gen.next()
            if stopevent.is_set():
                break
            self.cb()
        logger.info('timer stopped')

    def get_next_time(self, now):
        self.cur_time = now
        self.next_time = now + self.incr_time
        while True:
            yield self.cur_time, self.next_time
            self.cur_time = monotonic_time(self.raw)
            while self.next_time < self.cur_time:
                self.next_time += self.incr_time

if __name__ == '__main__':
    import time
    import math

    def print_time():
        t = time.time()
        if int(t) % 5 == 0:
            math.factorial(50000)

        print t

    pt = PeriodicTimer(1, print_time)
    import threading
    pt.loop(threading.Event())
