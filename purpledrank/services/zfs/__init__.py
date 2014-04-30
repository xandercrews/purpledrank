__author__ = 'achmed'

import subprocess

from ..baseservice import BaseService
import zerorpc
from gevent import sleep

class ZFSService(BaseService):
    def hello(self):
        return 'hello'

    @zerorpc.stream
    def load_stats(self):
        while True:
            p = subprocess.Popen('/usr/gnu/bin/uptime', stdout=subprocess.PIPE)
            out, err = p.communicate()
            avgs = out.rsplit(':', 1)[1]
            yield map(float, map(str.strip, avgs.split(', ')))
            sleep(1)
