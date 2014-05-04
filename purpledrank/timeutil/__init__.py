__author__ = 'achmed'

import pytz
import datetime

def utctimestamp():
    return utcdatetime().isoformat()

def utcdatetime():
    return datetime.datetime.now(pytz.UTC)