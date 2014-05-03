__author__ = 'achmed'

from .. import timeutil

def make_envelope(_id, _type, sourceid, _d, timestamp=None):
    if timestamp is None:
        timestamp=timeutil.utctimestamp()
    return dict(
        id=_id,
        timestamp=timestamp,
        sourceid=sourceid,
        type=_type,
        _=_d
    )