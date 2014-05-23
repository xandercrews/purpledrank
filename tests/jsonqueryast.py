__author__ = 'achmed'

"""
design goals
------------
* wire up the AST with the data stream- somehow the stream needs to be fed with data to operate on
* provide a test method that can be used to evaluate some dataset against it

optimizations
-------------
* the query logic should only be run on a minimal subset of elements
* collapse updates into iterations to try and catch up, performance degrades and latency becomes equal
to the duration of full updates (like at startup)
** the relational criteria could be sorted in the order of average run time and short circuited
* at the very least, it should be possible to distribute queries (not split, just distribute) amongst workers
** queries should be able to be split amongst several workers.  (how?)


interfaces (query from the objects)
----------
a method to cause it to query the entire dataset
a method to cause it to refresh just the subset of the data which might be affected by an update (i.e. in
response to a notification)
adapter for providing the AST with a way to fetch data from the backend

interfaces (query engine helpers)
----------
a method to find the key prefixes to know what to subscribe to
a way to map the free variables (to what?)
a way to extract the paths that will be used for relating

query engine procedure
----------
(init and sync)
take note of the prefixes that are to be monitored
look for the relational criteria that is part of the query, and link it to a key prefix
mark all existing link nodes for the query (?)
mark all existing relations for the query
iterate over the keys in the key prefixes, and transform the relational criteria for each node into a shared key for an intermediate link node
add or remove link node under query-specific key prefix and remove mark
sweep pre-existing, unmarked link nodes for a given query
(updates)
read subscriptions off queue
transform the relational criteria for each node into a shared key for an intermediate link node
create or update link nodes according to the calculated keys

link node key generator
-----------
[this isn't perfect but i think it will work for starters]
pick arbitrarily the node that will be used for collecting criteria (let's say the predecessor)
collect all of the json paths (or whatever the method of extraction is) in a stable order,
there will be an array for each, which may contain one element
take the cartesian product of those results, yield tuples
null (\0) join the tuples into strings, hash the strings (with pyhashxx - some fast hash, non-cryptographic OK)
combine the result with a
"""

import atexit
import collections
import redis
import functools
import itertools
import fnmatch
import jsonpath_rw
import pyhashxx
import UserDict
import operator
import re

from purpledrank.purpleutil import dictequal
from purpledrank.redisutil import scan_iter, add_prefix

# import msgpack as endecoder
import json as endecoder

import purpledrank.log
purpledrank.log.init_logger()

import logging
logger = logging.getLogger('jsonqueryast')


class NYI(Exception):
    pass


def memoize(obj):
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer


class StreamQueryAST(object):
    def __init__(self, parent):
        assert parent is None or isinstance(parent, StreamQueryAST), 'parent must also be a streamqueryast object'
        self.parent = parent


class InitialStreamNode(StreamQueryAST):
    def __init__(self):
        StreamQueryAST.__init__(self, None)


class TerminalStreamNode(StreamQueryAST):
    def __init__(self, parent):
        StreamQueryAST.__init__(self, parent)

    def _find_head(self):
        p = self.parent
        while not isinstance(p, InitialStreamNode):
            assert p is not None, 'reached first node in query before finding an initial node'
            p = p.parent

        return p

    @classmethod
    def _find_classes(cls, c, o):
        if isinstance(o, collections.Sequence):
            for i in o:
                for x in cls._find_classes(c, i):
                    yield x

        if o.__class__ == c:
            yield o

        if hasattr(o, 'select_sources'):
            for x in cls._find_classes(c, o.select_sources):
                yield x
        if hasattr(o, 'join_criteria'):
            for x in cls._find_classes(c, o.join_criteria):
                yield x
        if hasattr(o, 'operands'):
            for x in cls._find_classes(c, o.operands):
                yield x
        if hasattr(o, 'parent'):
            for x in cls._find_classes(c, o.parent):
                yield x
        if hasattr(o, 'predecessor'):
            for x in cls._find_classes(c, o.predecessor):
                yield x
        if hasattr(o, 'successor'):
            for x in cls._find_classes(c, o.successor):
                yield x
        if hasattr(o, 'left'):
            for x in cls._find_classes(c, o.left):
                yield x
        if hasattr(o, 'right'):
            for x in cls._find_classes(c, o.right):
                yield x
        if hasattr(o, 'var'):
            for x in cls._find_classes(c, o.var):
                yield x

    def get_key_prefixes(self):
        # head = self._find_head()

        froms = list(self._find_classes(From, self))

        return [ f.pattern for f in froms ]

    def get_select_criteria(self):
        selects = list(self._find_classes(Select, self))

        assert len(selects) == 1, 'expected one select statement'

        return selects[0].select_sources

    def get_join_criteria(self):
        joins = list(self._find_classes(Join_On, self))

        assert len(joins) == 1, 'expected one join statement'

        return joins[0].join_criteria

    def get_relation_node(self):
        relates = list(self._find_classes(Relate, self))

        assert 0 <= len(relates) <= 1, 'expected 0 or 1 relate statements'

        if len(relates) == 1:
            return relates[0]
        else:
            return None

    def get_merge_node(self):
        merges = list(self._find_classes(Merge, self))

        assert 0 <= len(merges) <= 1, 'expected 0 or 1 merge statements'

        if len(merges) == 1:
            return merges[0]
        else:
            return None

    def get_free_variables(self):
        # head = self._find_head()

        frees = list(self._find_classes(Free, self))

        return frees


class Select(InitialStreamNode):
    def __init__(self, *select_sources):
        InitialStreamNode.__init__(self)
        self.select_sources = select_sources

    def Join_On(self, *args):
        return Join_On(self, *args)


class Join_On(StreamQueryAST):
    def __init__(self, parent, *join_criteria):
        # join criteria are treated as being in CNF, and there's an Or
        # operator for alternation
        StreamQueryAST.__init__(self, parent)
        self.join_criteria = join_criteria

    def Relate(self, *args):
        return Relate(self, *args)

    def Merge(self, *args):
        return Merge(self, *args)


class Relate(TerminalStreamNode):
    def __init__(self, parent, predecessor, label, successor):
        TerminalStreamNode.__init__(self, parent)
        self.predecessor = predecessor
        self.label = label
        self.successor = successor


class Merge(TerminalStreamNode):
    def __init__(self, parent, merge_action):
        TerminalStreamNode.__init__(self, parent)


class Call_table_method(StreamQueryAST):
    def __init__(self, method_name, *operands):
        StreamQueryAST.__init__(self, None)
        self.method_name = method_name
        self.operands = operands

    def From(self, pattern):
        raise Exception('NYI')


class Free(StreamQueryAST):
    def __init__(self, identifier):
        StreamQueryAST.__init__(self, None)
        self.identifier = identifier

    def From(self, pattern):
        return From(self, pattern)


class From(StreamQueryAST):
    def __init__(self, parent, pattern):
        StreamQueryAST.__init__(self, parent)
        self.pattern = pattern


class In(StreamQueryAST):
    def __init__(self, left, right):
        StreamQueryAST.__init__(self, None)
        self.left = left
        self.right = right


class Equals(StreamQueryAST):
    def __init__(self, left, right):
        StreamQueryAST.__init__(self, None)
        self.left = left
        self.right = right


class Json_path(StreamQueryAST):
    def __init__(self, var, pattern):
        StreamQueryAST.__init__(self, None)
        self.var = var
        self.pattern = pattern


class Static(StreamQueryAST):
    def __init__(self, val):
        StreamQueryAST.__init__(self, None)
        self.val = val


class Or(StreamQueryAST):
    def __init__(self, alternates):
        StreamQueryAST.__init__(self, None)


class RedisQuery(object):
    JSON_PATH = 1
    CALL_TABLE_JSON_PATH = 2
    STATIC = 3

    def __init__(self, q, qid, call_table):
        logger.info('creating new query id=%d' % qid)
        self.q = q
        self.qid = qid
        self.initialized = False
        self.call_table = call_table

    @memoize
    def keyPrefixMap(self):
        pmap = {}

        for s in self.q.get_select_criteria():
            assert s.__class__ == From, 'expected select criteria is from pattern'

            rels = []

            if s.parent.__class__ == Free:
                # find relational criteria
                freevar = s.parent.identifier

                for j in self.q.get_join_criteria():
                    if j.__class__ == Equals:
                        pass
                    elif j.__class__ == In:
                        pass
                    else:
                        raise NYI('join criteria type %s' % str(j.__class__))

                    if bool(j.left.__class__ == Static) ^ bool(j.right.__class__ == Static):
                        if j.left.__class__ == Static:
                            static = j.left
                            jp = j.right
                        else:
                            static = j.right
                            jp = j.left
                        assert jp.__class__ == Json_path
                        if jp.var.identifier == freevar:
                            vargs = (self.STATIC, jp.pattern, static.val)
                            rels.append(vargs)
                    elif j.left.__class__ != Static and j.right.__class__ != Static:
                        for v in (j.left, j.right):
                            if v.__class__ == Json_path:
                                if v.var.identifier == freevar:
                                    vargs = (self.JSON_PATH, v.pattern)
                                    rels.append(vargs)
                            elif v.__class__ == Call_table_method:
                                # TODO process more complicated arrangements
                                if v.method_name not in self.call_table:
                                    raise Exception('call table method %s not available' % v.method_name)

                                if v.operands[0].var.identifier == freevar:
                                    vargs = (self.CALL_TABLE_JSON_PATH, self.call_table[v.method_name], v.operands[0].pattern)
                                    rels.append(vargs)
                            else:
                                raise NYI('join variable type %s' % str(v.__class__))
                    else:
                        raise NYI('two static operands')

            else:
                raise NYI('select criteria type %s' % str(s.parent.__class__))

            pmap[s.pattern] = rels

        logger.debug('prefix map for qid=%d: %s' % (self.qid, str(pmap)))
        return pmap

    @memoize
    def relation_patterns(self):
        relate = self.q.get_relation_node()

        if relate is None:
            return None

        p = relate.predecessor
        s = relate.successor

        assert p.__class__ == Free, 'expected predecessor is Free variable'
        assert s.__class__ == Free, 'expected successor is Free variable'

        pvar = p.identifier
        svar = s.identifier

        relmap = {}

        for c in self.q.get_select_criteria():
            assert c.__class__ == From, 'expected select criteria is From pattern'
            pat = c.pattern

            assert c.parent.__class__ == Free, 'expected Free variable in select pattern'
            if c.parent.identifier == pvar:
                relmap['p'] = dict(var=c.parent.identifier, pattern=pat)
            else:
                assert c.parent.identifier == svar
                relmap['s'] = dict(var=c.parent.identifier, pattern=pat)

        return relmap

    @memoize
    def linkNodePrefix(self):
        return '_link\0%s' % self.actionLabel()

    @memoize
    def actionLabel(self):
        relate = self.q.get_relation_node()
        merge = self.q.get_merge_node()

        assert bool(relate is None) ^ bool(merge is None), 'only one of relate or merge node should be present'

        if relate is not None:
            label = relate.label
        else:
            raise NYI('merge identifier')

        return label

    @memoize
    def outDocNodePrefix(self):
        return self.actionLabel()

    @memoize
    def linkIndexPrefix(self):
        return '_indexlink\0%s' % self.actionLabel()

    @memoize
    def linkNodeHashFunc(self):
        pmap = self.keyPrefixMap()

        extractors = {p: [] for p in pmap.keys()}

        for pat, val in pmap.items():
            for t in val:
                def jsonExtractor(path):
                    e = jsonpath_rw.parse(path)
                    def g(o):
                        return filter(None, [getattr(v, 'value') for v in e.find(o)])
                    return g

                # TODO handle more complicated arrangements
                def callTableJsonExtractor(table_method, path):
                    e = jsonpath_rw.parse(path)
                    def g(o):
                        vals = filter(None, [getattr(v, 'value') for v in e.find(o)])
                        return map(table_method, vals)
                    return g

                def staticValueChecker(path, val):
                    e = jsonpath_rw.parse(path)
                    def g(o):
                        vals = filter(None, [getattr(v, 'value') for v in e.find(o)])
                        vals = map(lambda v: v == val, vals)
                        if True in vals:
                            return True
                        return False
                    return g

                typecode = t[0]

                if typecode == self.JSON_PATH:
                    _, path = t
                    extractors[pat].append(jsonExtractor(path))
                elif typecode == self.CALL_TABLE_JSON_PATH:
                    _, methodname, path = t
                    extractors[pat].append(callTableJsonExtractor(methodname, path))
                elif typecode == self.STATIC:
                    _, path, val = t
                    extractors[pat].append(staticValueChecker(path, val))
                else:
                    raise NYI('other types of extractors')

        def g(key, obj):
            for pat, e in extractors.items():
                if fnmatch.fnmatch(key, pat):
                    unhashable = False
                    vals = []

                    for f in e:
                        v = f(obj)
                        if isinstance(v, bool):
                            if not v:
                                unhashable = True
                                break
                        else:
                            vals.append(f(obj))

                    if unhashable:
                        logger.debug('pat %s obj %s is unhashable' % (pat, key))
                        continue

                    for v in itertools.product(*vals):
                        s = str('\0'.join(v))
                        logger.debug('hash string for %s %s' % (key, s))
                        yield pyhashxx.hashxx(s), s
                    break

        return g


class RedisQueryEngine(object):
    def __init__(self, host, port, db=0):
        logger.info('connecting to redis')
        self.rconn = redis.StrictRedis(host=host, port=port, db=db)

        atexit.register(self._disconnectRedis)

        self.queries = []
        self.key_prefixes = {}
        self.subscriptions = {}

        self.pubsub = self.rconn.pubsub()

        self.qnum = 0

        self.call_table = QueryCallTable()

    def _disconnectRedis(self):
        logger.info('closing redis connections')
        self.rconn.connection_pool.disconnect()

    def addQuery(self, q):
        rq = RedisQuery(q, self.qnum, self.call_table)
        self.qnum += 1

        self.queries.append(rq)

        for prefix in rq.keyPrefixMap().keys():
            self._addKeyPrefix(prefix, rq.qid)

    def removeQuery(self, qid):
        # remove query by QID, and remove qid references in monitored key prefixes
        # any key prefix that has no more QID references can be cleaned up as well
        raise NYI('query removes')

    def initialQueries(self):
        for query in self.queries:
            if not query.initialized:
                self._runQueryAll(query)
                query.initialized = True

    def updateSubscriptions(self):
        for p in self.key_prefixes.keys():
            if p not in self.subscriptions:
                self.subscriptions[p] = self.pubsub.psubscribe(p)

    def _markLinkKeys(self, keyprefix):
        # find link keys
        linkkeys = {k: 1 for k in scan_iter(self.rconn, keyprefix)}

        # find subkeys
        for key in linkkeys:
            linkkeys[key] = {k: 1 for k in self.rconn.hkeys(key)}

        return linkkeys

    def _sweepLinkKeys(self, linkmap):
        linkrels = set()

        for key, subkeys in linkmap.items():
            # sweep remaining subkeys of key
            if len(subkeys) == 0:
                continue

            while True:
                try:
                    with self.rconn.pipeline() as p:

                        p.multi()
                        for skey in subkeys:
                            self.rconn.hdel(key, skey)
                            linkrels.add(key)
                        p.execute()

                        logger.info('removed stale link node %s entries %s' % (key, ','.join(subkeys)))

                    self.rconn.publish(key, '')
                    break
                except redis.WatchError:
                    pass

        return linkrels

    def _runQueryAll(self, query):
        linknodeprefix = query.linkNodePrefix()
        pmap = query.keyPrefixMap()

        # find existing keys (mark)
        linkkeys = self._markLinkKeys('%s\0*' % linknodeprefix)

        relatekeys = set()

        # iterate over each key from the prefixes
        for key in itertools.chain(*[scan_iter(self.rconn, p) for p in pmap.keys()]):
            v = self.rconn.get(key)
            v = endecoder.loads(v)

            hasher = query.linkNodeHashFunc()
            linkhashes = dict(hasher(key, v))

            for h, criteria in linkhashes.items():
                linkkey, changed = self._addOrUpdateLinkNode(linknodeprefix, key, h, criteria)
                if changed:
                    relatekeys.add(linkkey)
                try:
                    del linkkeys[linkkey][key]
                except:
                    pass

                if linkkey in linkkeys and len(linkkeys[linkkey]) == 0:
                    del linkkeys[linkkey]

        # remove remaining keys (sweep)
        dellinks = self._sweepLinkKeys(linkkeys)
        relatekeys.update(dellinks)

        # make relations nodes from link nodes
        for k in relatekeys:
            self._relateStep(query, k)

    def _runQueryOnce(self, query, key, v):
        linknodeprefix = query.linkNodePrefix()
        pmap = query.keyPrefixMap()

        for p in pmap.keys():
            if fnmatch.fnmatch(key, p):
                # mark
                linkkeys = self._markLinkKeys('%s\0*' % linknodeprefix)

                for linkkey, subkeys in linkkeys.items():
                    linkkeys[linkkey] = { sk: 1 for sk in filter(lambda k: k == key, subkeys.keys()) }
                    if len(linkkeys[linkkey]) == 0:
                        del linkkeys[linkkey]

                relatekeys = set()

                if '_' in v and v['_'] is None:
                    # this is a deletion, no need to evaluate for links, just let it sweep existing links
                    logger.debug('received delete notification for %s' % key)
                else:
                    # this is an update
                    hasher = query.linkNodeHashFunc()
                    linkhashes = dict(hasher(key, v))

                    for h, criteria in linkhashes.items():
                        linkkey, changed = self._addOrUpdateLinkNode(linknodeprefix, key, h, criteria)

                        if changed:
                            relatekeys.add(linkkey)

                        try:
                            del linkkeys[linkkey][key]
                        except:
                            pass

                        if linkkey in linkkeys and len(linkkeys[linkkey]) == 0:
                            del linkkeys[linkkey]

                # sweep
                dellinks = self._sweepLinkKeys(linkkeys)
                relatekeys.update(dellinks)

                # make relations from link nodes
                for k in relatekeys:
                    self._relateStep(query, k)

                break


    def _addOrUpdateLinkNode(self, linknodeprefix, key, h, criteria):
        # logger.debug('%s:%s -> %s (%s)' % (linknodeprefix, h, key, criteria))
        linkkey = add_prefix(linknodeprefix, str(h))
        changed = False
        while True:
            try:
                with self.rconn.pipeline() as p:
                    p.watch(linkkey)
                    old_criteria = p.hget(linkkey, key)
                    p.multi()
                    if old_criteria != criteria:
                        p.hset(linkkey, key, criteria)
                        changed = True
                    else:
                        # logger.debug('no change to link key %s' % linkkey)
                        break
                    p.execute()

                logger.info('publishing update to link node %s, %s' % (linkkey, key))
                self.rconn.publish(linkkey, '')

                break
            except redis.WatchError, e:
                pass
        return linkkey, changed

    def _addKeyPrefix(self, p, qid):
        if p in self.key_prefixes:
            logger.info('found duplicate key prefix %s' % p)
            self.key_prefixes[p].append(qid)
        else:
            logger.info('found new key prefix %s' % p)
            self.key_prefixes[p] = [qid]

    def _relateStep(self, query, linkkey):
        relmap = query.relation_patterns()
        if relmap is None:
            return

        relns = []

        links = self.rconn.hgetall(linkkey)
        if links is not None:
            # pair up the criteria
            reverse_links = {}
            for dkey, criteria in links.items():
                keys = reverse_links.setdefault(criteria, [])
                keys.append(dkey)

            for criteria, keys in reverse_links.items():
                preds = []
                succs = []
                for key in keys:
                    if fnmatch.fnmatch(key, relmap['p']['pattern']):
                        preds.append(key)
                    else:
                        assert fnmatch.fnmatch(key, relmap['s']['pattern']), 'expected patterns present in the link node match those in the query'
                        succs.append(key)
                relns.extend(itertools.product(preds, succs))

            label = query.outDocNodePrefix()

        # mark relations
        indexkey = '\0'.join((query.linkIndexPrefix(), linkkey))
        linkrels = self._markRelations(indexkey)

        # insert relations, if any
        for r in relns:
            logger.debug('adding %s relation %s' % (label, r))
            d = dict(_from=r[0], _to=r[1], label=label, )
            rkey = self._addOrUpdateRelation(indexkey, query.outDocNodePrefix(), d)
            linkrels.discard(rkey)

        # sweep relations
        self._sweepRelations(indexkey, linkrels)

    def _addOrUpdateRelation(self, indexkey, prefix, d):
        rkey = '\0'.join((prefix, d['_from'], '\0' + d['_to']))

        while True:
            try:
                update_record = False

                with self.rconn.pipeline() as p:
                    p.watch(rkey)

                    r = p.get(rkey)

                    if r is None:
                        update_record = True
                    else:
                        old_data = endecoder.loads(r)

                        if not isinstance(old_data, collections.Mapping):
                            update_record = True
                        elif not dictequal(d, old_data):
                            update_record = True

                    if update_record:
                        p.multi()
                        d = endecoder.dumps(d)
                        p.set(rkey, d)
                        p.sadd(indexkey, rkey)
                        p.execute()
                        self.rconn.publish(prefix, d)

                break
            except redis.WatchError:
                pass

        return rkey

    def _markRelations(self, indexkey):
        return self.rconn.smembers(indexkey)

    def _sweepRelations(self, indexkey, rels):
        if len(rels) > 0:
            for key in rels:
                self.rconn.delete(key)
                logger.info('removed stale relation %s' % key)

            self.rconn.srem(indexkey, rels)

    def _mergeStep(self, query):
        pass

    def subscriptionLoop(self):
        while True:
            for item in self.pubsub.listen():
                if item['type'].endswith('subscribe'):
                    continue

                pattern, data = item['pattern'], item['data']
                v = endecoder.loads(data)

                assert pattern in self.key_prefixes

                qids = self.key_prefixes[pattern]
                for qid in qids:
                    query = filter(lambda q: operator.attrgetter('qid')(q) == qid, self.queries)
                    assert 0 <= len(query) <= 1
                    if len(query) == 0:
                        continue
                    query = query[0]
                    self._runQueryOnce(query, v['rkey'], v)


class QueryCallTable(UserDict.DictMixin):
    def __init__(self):
        self.table = {}

    def registerCall(self, label, f):
        if label not in self.table:
            self.table[label] = f
        else:
            raise Exception('call already registered')

    def __getitem__(self, item):
        return self.table[item]

    def keys(self):
        return self.table.keys()

    def __setitem__(self, item, val):
        self.registerCall(item, val)

    def __delitem__(self, key):
        raise NYI('unregister call table routine')


def zpool_from_zvol_id(zvolid):
    return zvolid.strip('/').split('/')[0]

slicepat = re.compile('(.*)(s\d+)$')

def strip_disk_slice(diskname):
    m = re.match(slicepat, diskname)

    if m is None:
        return diskname
    else:
        return m.group(1)

def strip_zvol_parentdir(datafile):
    PARENTDIR = '/dev/zvol/rdsk/'
    if datafile.startswith(PARENTDIR):
        return datafile[len(PARENTDIR):]
    return datafile

def main():
    # SELECT
    # flatten_disks(x) from zpool:*,
    # y from harddisk:*
    # JOIN ON
    # x._.id IN y._.disks,
    # x.sourceid == y.sourceid
    # RELATE
    # disk_relation(x, y)


    ####
    # A more complicated example with temporary keys
    ####

    # queryast = \
    #     Select(
    #         Call_table_method('flatten_disks', Free('x')).From('zpool:*'),
    #         Free('y').From('harddisk.*')
    #     ).Join_On(
    #         In(
    #             Json_path(Free('x'), '_.id'),
    #             Json_path(Free('y'), '_.disks')
    #         ),
    #         Equals(
    #             Json_path(Free('x'), 'sourceid'),
    #             Json_path(Free('y'), 'sourceid'),
    #             )
    #     ).Relate(
    #         Call_table_method('disk_relation', Free('x'), Free('y'))
    #     )
    #
    # p = queryast.get_key_prefixes()

    ###
    # A less complicated example
    ###

    # queryast = \
    #     Select(
    #         Free('x').From('zpool:*'),
    #         Free('y').From('harddisk.*'),
    #     ).Join_On(
    #         In(
    #             Json_path(Free('y'), '_.id'),
    #             Json_path(Free('x'), '_.disks[*]')
    #         ),
    #         Equals(
    #             Json_path(Free('x'), 'sourceid'),
    #             Json_path(Free('y'), 'sourceid'),
    #             )
    #     ).Relate(
    #         Free('x'), 'disk_of', Free('y')
    #     )

    ###
    # A example based on the real values in the redis store
    ###

    # SELECT
    # x FROM zpool_status\0*,
    # y FROM cfgadm_disks\0*
    # JOIN ON
    # y.id IN strip_disk_slice(x._..disks[*].name)
    # x.sourceid == y.sourceid
    # RELATE
    # x disk_of y

    disk_query = \
        Select(
            Free('x').From('zpool_status\0*'),
            Free('y').From('cfgadm_disks\0*'),
        ).Join_On(
            In(
                Json_path(Free('y'), 'id'),
                Call_table_method('strip_disk_slice', Json_path(Free('x'), '_..disks[*].name')),
            ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
            ),
            Equals(
                Json_path(Free('x'), 'type'),
                Static('zpool_status')
            ),
            Equals(
                Json_path(Free('y'), 'type'),
                Static('cfgadm_disks')
            )
        ).Relate(
            Free('x'), 'disk_of', Free('y')
        )

    zvol_query = \
        Select(
            Free('x').From('zvol_properties\0*'),
            Free('y').From('zpool_status\0*'),
        ).Join_On(
            Equals(
                Json_path(Free('y'), 'id'),
                Call_table_method('zpool_from_zvol_id', Json_path(Free('x'), 'id')),
            ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
            ),
            Equals(
                Json_path(Free('x'), 'type'),
                Static('zvol_properties')
            ),
            Equals(
                Json_path(Free('y'), 'type'),
                Static('zpool_status')
            )
        ).Relate(
            Free('x'), 'zvol_of', Free('y')
        )

    zpool_prop_query = \
        Select(
            Free('x').From('zpool_props\0*'),
            Free('y').From('zpool_status\0*'),
        ).Join_On(
            Equals(
                Json_path(Free('y'), 'id'),
                Call_table_method('zpool_from_zvol_id', Json_path(Free('x'), 'id')),
            ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
            ),
            Equals(
                Json_path(Free('x'), 'type'),
                Static('zpool_properties')
            ),
            Equals(
                Json_path(Free('y'), 'type'),
                Static('zpool_status')
            )
        ).Relate(
            Free('x'), 'zpool_properties_of', Free('y')
        )

    stmf_lun_vol = \
        Select(
            Free('x').From('stmf_targets\0*\0stmf_luns\0*'),
            Free('y').From('zvol_properties\0*')
        ).Join_On(
            Equals(
                Call_table_method('strip_zvol_parentdir', Json_path(Free('x'), '_.data_file')),
                Json_path(Free('y'), 'id')
            ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
            ),
            Equals(
                Json_path(Free('x'), 'type'),
                Static('stmf_luns')
            ),
            Equals(
                Json_path(Free('y'), 'type'),
                Static('zvol_properties')
            )
        ).Relate(
            Free('x'), 'lun_of', Free('y')
        )

    target_tpg = \
        Select(
            Free('x').From('itadm_properties\0*\0itadm_tpgs\0*'),
            Free('y').From('itadm_properties\0*\0itadm_targets\0*'),
        ).Join_On(
            Equals(
                Json_path(Free('x'), 'id'),
                Json_path(Free('y'), '_.tpg'),
            ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
                ),
            Equals(
                Json_path(Free('x'), 'type'),
                Static('itadm_tpgs')
            ),
            Equals(
                Json_path(Free('y'), 'type'),
                Static('itadm_targets')
            )
        ).Relate(
            Free('x'), 'tpg_of', Free('y')
        )

    lun_hg = \
        Select(
            Free('x').From('stmf_targets\0*\0stmf_luns\0*'),
            Free('y').From('stmf_targets*\0*\0stmf_hgs\0*'),
        ).Join_On(
            Equals(
                Json_path(Free('x'), '_.views..host_group[*]'),
                Json_path(Free('y'), 'id'),
                ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
                ),
            Equals(
                Json_path(Free('x'), 'type'),
                Static('stmf_luns')
            ),
            Equals(
                Json_path(Free('y'), 'type'),
                Static('stmf_hgs')
            )
        ).Relate(
            Free('x'), 'hg_of', Free('y')
        )

    rqe = RedisQueryEngine('localhost', 6379)
    rqe.call_table['zpool_from_zvol_id'] = zpool_from_zvol_id
    rqe.call_table['strip_disk_slice'] = strip_disk_slice
    rqe.call_table['strip_zvol_parentdir'] =  strip_zvol_parentdir
    rqe.addQuery(disk_query)
    rqe.addQuery(zvol_query)
    rqe.addQuery(zpool_prop_query)
    rqe.addQuery(stmf_lun_vol)
    rqe.addQuery(target_tpg)
    rqe.addQuery(lun_hg)
    rqe.updateSubscriptions()
    rqe.initialQueries()
    rqe.subscriptionLoop()

if __name__ == '__main__':
    main()

# vim: set ts=4 sw=4 filetype=python expandtab:
