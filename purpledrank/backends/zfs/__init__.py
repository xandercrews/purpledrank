__author__ = 'achmed'

import sys
import subprocess

import grammars.zpoolstatus
import util

if sys.platform.startswith('sunos'):
    ZPOOL_CMD = '/usr/sbin/zpool'
else:
    assert sys.platform.startswith('linux')
    ZPOOL_CMD = '/usr/bin/zpool'

from ...log import init_logger
init_logger()

import logging
logger = logging.getLogger()

def get_zpool_status(self):
    p = subprocess.Popen([ZPOOL_CMD, 'status',], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
    out, err = p.communicate()
    logger.debug('zpool status output\n' + out)

    if p.returncode != 0:
        raise Exception('zpool status command failed: %s' % err)

    parser = grammars.zpoolstatus.LanguageOfZpoolStatuses.parser()
    r = parser.parse_string(out, eof=True)

    if r is None:
        raise Exception('unknown problem parsing zpool status')

    logger.debug('parser remainder\n' + parser.remainder())

    return util.get_zpool_tree(r)
