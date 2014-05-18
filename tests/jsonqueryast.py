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
"""

import atexit
import collections
import redis

import purpledrank.log
purpledrank.log.init_logger()

import logging
logger = logging.getLogger('jsonqueryast')


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

    def _find_parent(self):
        p = self.parent
        while not isinstance(p, InitialStreamNode):
            assert p is not None, 'reached first node in query before finding an initial node'
            p = p.parent

        return p

    def _find_classes(self, c, o):
        if isinstance(o, collections.Sequence):
            for i in o:
                for x in self._find_classes(c, i):
                    yield x

        if o.__class__ == c:
            yield o

        if hasattr(o, 'select_sources'):
            for x in self._find_classes(c, o.select_sources):
                yield x
        elif hasattr(o, 'join_criteria'):
            for x in self._find_classes(c, o.join_criteria):
                yield x
        elif hasattr(o, 'operands'):
            for x in self._find_classes(c, o.operands):
                yield x

    def get_key_prefixes(self):
        p = self._find_parent()

        froms = list(self._find_classes(From, p))

        return [ f.pattern for f in froms ]


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

    def From(self, pattern):
        return From(self, pattern)


class From(StreamQueryAST):
    def __init__(self, parent, pattern):
        StreamQueryAST.__init__(self, parent)
        self.pattern = pattern


class In(StreamQueryAST):
    def __init__(self, left, right):
        StreamQueryAST.__init__(self, None)


class Equals(StreamQueryAST):
    def __init__(self, left, right):
        StreamQueryAST.__init__(self, None)


class Json_path(StreamQueryAST):
    def __init__(self, var, pattern):
        StreamQueryAST.__init__(self, None)


class Or(StreamQueryAST):
    def __init__(self, alternates):
        StreamQueryAST.__init__(self, None)


class RedisQuery(object):
    def __init__(self, q, qid):
        logger.info('creating new query id=%d' % qid)
        self.q = q
        self.qid = qid


class RedisQueryEngine(object):
    def __init__(self, host, port, db=0):
        logger.info('connecting to redis')
        self.rconn = redis.StrictRedis(host=host, port=port, db=db)

        atexit.register(self._disconnectRedis)

        self.queries = []
        self.key_prefixes = {}

        self.qnum = 0

        self.calltable = QueryCallTable()

    def _disconnectRedis(self):
        logger.info('closing redis connections')
        self.rconn.connection_pool.disconnect()

    def addQuery(self, q):
        rq = RedisQuery(q, self.qnum)
        self.qnum += 1

        self.queries.append(rq)

        for p in rq.q.get_key_prefixes():
            self._addKeyPrefix(p, rq.qid)

    def _addKeyPrefix(self, p, qid):
        if p in self.key_prefixes:
            logger.info('found duplicate key prefix %s' % p)
            self.key_prefixes[p].append(qid)
        else:
            logger.info('found new key prefix %s' % p)
            self.key_prefixes[p] = [qid]


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

    queryast = \
        Select(
            Free('x').From('zpool:*'),
            Free('y').From('harddisk.*'),
        ).Join_On(
            In(
                Json_path(Free('y'), '_.id'),
                Json_path(Free('x'), '_.disks')
            ),
            Equals(
                Json_path(Free('x'), 'sourceid'),
                Json_path(Free('y'), 'sourceid'),
                )
        ).Relate(
            Free('x'), 'disk_of', Free('y')
        )

    rqe = RedisQueryEngine('localhost', 6379)
    rqe.addQuery(queryast)

if __name__ == '__main__':
    main()


# vim: set ts=4 sw=4 filetype=python expandtab:
