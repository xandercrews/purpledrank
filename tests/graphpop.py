__author__ = 'achmed'


import requests
import redis
import itertools
import functools
import json


doc_prefixes = [
    "zvol_properties",
    "cfgadm_disks",
    "stmf_targets",
    "kvm_vms",
    "zpool_props",
    "zpool_status",
    "itadm_properties",
]

rel_prefixes = [
    "tpg_of",
    "zvol_of",
    "hg_of",
    "disk_of",
    "lun_of",
    "remotelun_of",
    "zpool_properties_of",
]

QUERY_PREFIX = "http://tools.svcs.aperobot.net:8529/_db/purpledrank"


def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    count = 0
    accum = []

    for i in l:
        accum.append(i)
        count += 1
        if count % n == 0:
            yield accum
            count = 0
            accum = []

    if len(accum) > 0:
        yield accum


def get_docs(rconn, keyiter):
    for k in keyiter:
        yield rconn.get(k)


s = requests.Session()
c = redis.StrictRedis(host='tools.svcs.aperobot.net', port=6379)

getter = functools.partial(get_docs, c)

# create docs
for d in map(getter, chunks(itertools.chain(*map(c.scan_iter, map(lambda s: '%s\0*' % s, doc_prefixes))), 20)):
    def decode_and_mutate(j):
        j = json.loads(j)
        j['data'] = j['_']
        return j
    # r = s.post('%s/_api/import?collection=purpledoc&type=array&details=true' % QUERY_PREFIX, data=json.dumps(list(map(decode_and_mutate, d))))
    r = s.post('%s/_api/import?collection=purpledoc&type=array' % QUERY_PREFIX, data=json.dumps(list(map(decode_and_mutate, d))))
    print r, r.text


# TODO use a cursor
# build an ID map
r = s.post('%s/_api/cursor' % QUERY_PREFIX, data=json.dumps(dict(query='FOR d IN purpledoc RETURN [ d.rkey, d._id ]')))
j = r.json()
keymap = dict(j['result'])

# build a hash of existing relations
r = s.post('%s/_api/cursor' % QUERY_PREFIX, data=json.dumps(dict(query='FOR e IN purpleedge RETURN [ e._from, e._to, e._label ]')))
j = r.json()
edgemap = { tuple(k): 1 for k in j }

# create edges
for d in map(getter, chunks(itertools.chain(*map(c.scan_iter, map(lambda s: '%s\0*' % s, rel_prefixes))), 20)):
    def decode_and_translate(j):
        j = json.loads(j)

        _from = j['_from']
        _to = j['_to']
        j['_from'] = keymap[_from]
        j['_to'] = keymap[_to]

        if (j['_from'], j['_to'], j['label'],) in edgemap:
            return j
        else:
            return None

    data = list(filter(None, map(decode_and_translate, d)))

    if len(data) > 0:
        print len(data), data
        # r = s.post('%s/_api/import?collection=purpleedge&type=array&details=true' % QUERY_PREFIX, data=json.dumps(data))
        r = s.post('%s/_api/import?collection=purpleedge&type=array' % QUERY_PREFIX, data=json.dumps(data))
        print r, r.text
