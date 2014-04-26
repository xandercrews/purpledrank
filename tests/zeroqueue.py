__author__ = 'achmed'

import zerorpc
import IPython

s = zerorpc.Client()
s.connect('tcp://127.0.0.1:9292')

IPython.embed()
