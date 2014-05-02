__author__ = 'achmed'

import sys

import grammars.zpoolstatus
import util

if sys.platform.startswith('sunos'):
    ZPOOL_CMD = '/usr/sbin/zpool'
    ZFS_CMD = '/usr/sbin/zfs'
else:
    assert sys.platform.startswith('linux')
    ZPOOL_CMD = '/usr/bin/zpool'
    ZFS_CMD = '/usr/sbin/zfs'

from ...log import init_logger
init_logger()

import logging
logger = logging.getLogger()

import re

class ZFSDataInterface(object):
    @classmethod
    def zfs_volume_properties(cls):
        result = util._generic_command(ZFS_CMD, 'list', '-t', 'volume', '-o', 'name')
        lines = result.splitlines()

        # check header
        assert map(str.strip, lines[0].split()) == ['NAME',], 'unexpected fields in header'

        volumes = []

        # collect names
        for line in lines[1:]:
            fields = map(str.strip, line.split())
            assert len(fields) == 1, 'unexpected fields in results'
            volumes.append(fields[0])

        # get properties
        result = util._generic_command(ZFS_CMD, 'get', '-Hp', '-r', '-t', 'snapshot,volume', 'all', *volumes)
        lines = result.splitlines()

        return cls._parse_properties(lines, scriptmode=True)

    @classmethod
    def zpool_properties(cls, pool=None):
        args = [ZPOOL_CMD, 'get', 'all']

        if pool is not None:
            r = re.match('^[a-zA-Z0-9]+$', pool)
            if r is None:
                raise Exception('invalid pool name')

            args.append(pool)

        result = util._generic_command(*args)
        lines = result.splitlines()

        return cls._parse_properties(lines)

    @classmethod
    def zpool_status(cls, pool=None):
        args = [ZPOOL_CMD, 'status',]

        if pool is not None:
            r = re.match('^[a-zA-Z0-9]+$', pool)
            if r is None:
                raise Exception('invalid pool name')

            args.append(pool)

        result = util._generic_command(*args)

        parser = grammars.zpoolstatus.LanguageOfZpoolStatuses.parser()
        r = parser.parse_string(result, eof=True)

        if r is None:
            raise Exception('unknown problem parsing zpool status')

        rem = parser.remainder()
        if len(rem) > 0:
            logger.error('zpool status parser succeeded but had unexpected trailing content')
            logger.debug(rem)
            raise Exception('incomplete status output parsing')

        return util.get_zpool_tree(r)

    @staticmethod
    def _parse_properties(lines, scriptmode=False):
        # check header if not in script mode
        if not scriptmode:
            assert map(str.strip, lines[0].split()) == ['NAME', 'PROPERTY', 'VALUE', 'SOURCE',], 'unexpected fields in header'

        names = {}

        # collect properties
        if scriptmode:
            line_iter = iter(lines)
        else:
            line_iter = iter(lines[1:])

        for line in line_iter:
            if scriptmode:
                name, propname, propvalue, source = line.split('\t')
            else:
                name, propname, rhs = map(str.strip, line.split(None, 2))
                propvalue, source = map(str.strip, rhs.rsplit(None, 1))
            if name not in names:
                names[name] = { propname: propvalue }
            else:
                names[name][propname] = propvalue

        return names
