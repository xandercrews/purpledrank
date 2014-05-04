__author__ = 'achmed'

from .. import timeutil

def make_envelope(_d, _id, _type, sourceid, timestamp=None):
    if timestamp is None:
        timestamp=timeutil.utctimestamp()
    return dict(
        id=_id,
        timestamp=timestamp,
        sourceid=sourceid,
        type=_type,
        _=_d
    )

def make_envelope_foreach(datahash, _type, sourceid, timestamp=None):
    enveloped_data = []

    for _id, _d in datahash.iteritems():
        enveloped_data.append(make_envelope(_d, _id, _type, sourceid, timestamp))

    return enveloped_data