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
import json
import fnmatch
import jsonpath_rw
import pyhashxx
import operator

from purpledrank.redisutil import scan_iter, make_prefix, add_prefix

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
    def __init__(self, methodname, *operands):
        StreamQueryAST.__init__(self, None)
        self.operands = operands

    def From(self, pattern):
        raise Exception('NYI')
        # return From(self, pattern)


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


class Or(StreamQueryAST):
    def __init__(self, alternates):
        StreamQueryAST.__init__(self, None)


class RedisQuery(object):

    def __init__(self, q, qid):
        logger.info('creating new query id=%d' % qid)
        self.q = q
        self.qid = qid
        self.initialized = False

    @memoize
    def keyPrefixMap(self):
        pmap = {}

        for s in self.q.get_select_criteria():
            assert s.__class__ == From, 'expected select criteria is from pattern'

            rels = collections.OrderedDict()

            if s.parent.__class__ == Free:
                # find relational criteria
                freevar = s.parent.identifier

                for j in self.q.get_join_criteria():
                    if j.__class__ == Equals:
                        jtype = j.__class__
                    elif j.__class__ == In:
                        jtype = j.__class__
                    else:
                        raise NYI('join criteria type %s' % str(j.__class__))

                    for v in (j.left, j.right):
                        if v.__class__ == Json_path:
                            vtype = v.__class__
                        else:
                            raise NYI('join variable type %s' % str(v.__class__))

                        if v.var.identifier == freevar:
                            rels[v.pattern] = 1

            else:
                raise NYI('select criteria type %s' % str(s.parent.__class__))

            pmap[s.pattern] = rels

        logger.debug('prefix map for qid=%d: %s' % (self.qid, str(pmap)))
        return pmap

    @memoize
    def linkNodePrefix(self):
        relate = self.q.get_relation_node()
        merge = self.q.get_merge_node()

        assert bool(relate is None) ^ bool(merge is None), 'only one of relate or merge node should be present'

        if relate is not None:
            label = relate.label
        else:
            raise NYI('merge identifier')

        logger.info('prefix for query q=%d output %s' % (self.qid, label))
        return label

    @memoize
    def linkNodeHashFunc(self):
        pmap = self.keyPrefixMap()

        extractors = {p: [] for p in pmap.keys()}

        for pat, val in pmap.items():
            for v in val:
                def datumExtractor(path):
                    e = jsonpath_rw.parse(path)
                    def g(o):
                        return filter(None, [getattr(v, 'value') for v in e.find(o)])
                    return g

                extractors[pat].append(datumExtractor(v))

        def g(key, obj):
            for pat, e in extractors.items():
                if fnmatch.fnmatch(key, pat):
                    vals = []

                    for f in e:
                        vals.append(f(obj))

                    for v in itertools.product(*vals):
                        s = str('\0'.join(v))
                        # logger.debug('hash string for %s %s' % (key, s))
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

        self.calltable = QueryCallTable()

    def _disconnectRedis(self):
        logger.info('closing redis connections')
        self.rconn.connection_pool.disconnect()

    def addQuery(self, q):
        rq = RedisQuery(q, self.qnum)
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
                        p.execute()

                        logger.info('removed stale link node %s entries %s' % (key, ','.join(subkeys)))
                        break
                except redis.WatchError:
                    pass

    def _runQueryAll(self, query):
        linknodeprefix = query.linkNodePrefix()
        pmap = query.keyPrefixMap()

        # find existing keys (mark)
        linkkeys = self._markLinkKeys('%s\0*' % linknodeprefix)

        # iterate over each key from the prefixes
        for key in itertools.chain(*[scan_iter(self.rconn, p) for p in pmap.keys()]):
            v = self.rconn.get(key)
            v = json.loads(v)

            hasher = query.linkNodeHashFunc()
            linkhashes = dict(hasher(key, v))

            for h, criteria in linkhashes.items():
                linkkey = self._addOrUpdateLinkNode(linknodeprefix, key, h, criteria)
                try:
                    del linkkeys[linkkey][key]
                except:
                    pass

                if linkkey in linkkeys and len(linkkeys[linkkey]) == 0:
                    del linkkeys[linkkey]

        # remove remaining keys (sweep)
        self._sweepLinkKeys(linkkeys)

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

                hasher = query.linkNodeHashFunc()
                linkhashes = dict(hasher(key, v))

                for h, criteria in linkhashes.items():
                    linkkey = self._addOrUpdateLinkNode(linknodeprefix, key, h, criteria)
                    try:
                        del linkkeys[linkkey][key]
                    except:
                        pass

                    if linkkey in linkkeys and len(linkkeys[linkkey]) == 0:
                        del linkkeys[linkkey]

                # sweep
                self._sweepLinkKeys(linkkeys)
                break

    def _addOrUpdateLinkNode(self, linknodeprefix, key, h, criteria):
        logger.info('%s:%s -> %s (%s)' % (linknodeprefix, h, key, criteria))
        linkkey = make_prefix(linknodeprefix, str(h))
        while True:
            try:
                with self.rconn.pipeline() as p:
                    p.watch(linkkey)
                    old_criteria = p.hget(linkkey, key)
                    p.multi()
                    if old_criteria != criteria:
                        p.hset(linkkey, key, criteria)
                    else:
                        # logger.debug('no change to link key %s' % linkkey)
                        break
                    p.execute()

                logger.info('publishing update to link node %s' % linkkey)
                self.rconn.publish(linkkey, '')

                break
            except redis.WatchError, e:
                pass
        return linkkey

    def _addKeyPrefix(self, p, qid):
        if p in self.key_prefixes:
            logger.info('found duplicate key prefix %s' % p)
            self.key_prefixes[p].append(qid)
        else:
            logger.info('found new key prefix %s' % p)
            self.key_prefixes[p] = [qid]

    def subscriptionLoop(self):
        while True:
            for item in self.pubsub.listen():
                if item['type'].endswith('subscribe'):
                    continue
                logger.info(item)
                pattern, data = item['pattern'], item['data']
                v = json.loads(data)


class QueryCallTable(object):
    def __init__(self):
        self.table = {}

    def registerCall(self, label, f):
        if label not in self.table:
            self.table[label] = f
        else:
            raise Exception('call already registered')


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

    disk_query = \
        Select(
            Free('x').From('zpool_status\0*'),
            Free('y').From('cfgadm_disks\0*'),
        ).Join_On(
            In(
                Json_path(Free('y'), 'id'),
                Json_path(Free('x'), '_..disks[*].name')
            ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
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
            )
        ).Relate(
            Free('x'), 'zvol_of', Free('y')
        )

    rqe = RedisQueryEngine('localhost', 6379)
    rqe.addQuery(disk_query)
    rqe.addQuery(zvol_query)
    rqe.updateSubscriptions()
    rqe.initialQueries()
    # rqe.subscriptionLoop()

if __name__ == '__main__':
    main()


# vim: set ts=4 sw=4 filetype=python expandtab:
