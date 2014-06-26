testdata =  """
  pool: rpool
 state: ONLINE
status: Some supported features are not enabled on the pool. The pool can
        still be used, but some features are unavailable.
action: Enable all features using 'zpool upgrade'. Once this is done,
        the pool may no longer be accessible by software that does not support
        the features. See zpool-features(5) for details.
  scan: scrub repaired 0 in 0h7m with 0 errors on Mon Jan  7 11:23:57 2013
config:

        NAME          STATE     READ WRITE CKSUM
        rpool         ONLINE       0     0     0
          mirror-0    ONLINE       0     0     0
            c3t0d0s0  ONLINE       0     0     0
            c4t1d0s0  ONLINE       0     0     0

errors: No known data errors

  pool: stor
 state: ONLINE
status: Some supported features are not enabled on the pool. The pool can
        still be used, but some features are unavailable.
action: Enable all features using 'zpool upgrade'. Once this is done,
        the pool may no longer be accessible by software that does not support
        the features. See zpool-features(5) for details.
  scan: scrub repaired 0 in 35h30m with 0 errors on Mon Jan 20 08:54:20 2014
config:

        NAME        STATE     READ WRITE CKSUM
        stor        ONLINE       0     0     0
          mirror-0  ONLINE       0     0     0
            c4t0d0  ONLINE       0     0     0
            c3t1d0  ONLINE       0     0     0
          mirror-1  ONLINE       0     0     0
            c4t3d0  ONLINE       0     0     0
            c3t2d0  ONLINE       0     0     0
          mirror-2  ONLINE       0     0     0
            c4t2d0  ONLINE       0     0     0
            c3t3d0  ONLINE       0     0     0
          mirror-3  ONLINE       0     0     0
            c4t5d0  ONLINE       0     0     0
            c3t4d0  ONLINE       0     0     0
          mirror-4  ONLINE       0     0     0
            c4t4d0  ONLINE       0     0     0
            c3t5d0  ONLINE       0     0     0
          mirror-5  ONLINE       0     0     0
            c4t7d0  ONLINE       0     0     0
            c3t6d0  ONLINE       0     0     0
        spares
          c4t6d0    AVAIL   

errors: No known data errors
""".strip('\n')

rpooldata = """
  pool: rpool
 state: ONLINE
status: Some supported features are not enabled on the pool. The pool can
        still be used, but some features are unavailable.
action: Enable all features using 'zpool upgrade'. Once this is done,
        the pool may no longer be accessible by software that does not support
        the features. See zpool-features(5) for details.
  scan: scrub repaired 0 in 0h7m with 0 errors on Mon Jan  7 11:23:57 2013
config:

        NAME          STATE     READ WRITE CKSUM
        rpool         ONLINE       0     0     0
          mirror-0    ONLINE       0     0     0
            c3t0d0s0  ONLINE       0     0     0
            c4t1d0s0  ONLINE       0     0     0

errors: No known data errors
""".lstrip('\n')

configdata = """
config:

        NAME          STATE     READ WRITE CKSUM
        rpool         ONLINE       0     0     0
          mirror-0    ONLINE       0     0     0
            c3t0d0s0  ONLINE       0     0     0
            c4t1d0s0  ONLINE       0     0     0

""".strip('\n')

import IPython

grammar_whitespace = False

from modgrammar import Grammar, REPEAT, WORD, OPTIONAL, L, OR
import modgrammar
import string

class SpaceSeperator(Grammar):
    grammar_greedy = True
    grammar = ( WORD(' '), )

class FieldWord(Grammar):
    grammar = ( WORD(string.ascii_letters + string.digits + string.punctuation) )

class FirstFieldValue(Grammar):
    grammar = ( FieldWord, OPTIONAL(REPEAT(SpaceSeperator, FieldWord)), L('\n'), )

class IndentedFieldValue(Grammar):
    grammar = ( OR('        ', '\t'), FirstFieldValue, )

class FullFieldValue(Grammar):
    grammar = ( FirstFieldValue, OPTIONAL(REPEAT(IndentedFieldValue)), )

class ErrorsField(Grammar):
    grammar = ( 'errors: ', FullFieldValue, )

class ConfigCounters(Grammar):
    grammar = ( WORD(string.digits), SpaceSeperator, WORD(string.digits), SpaceSeperator, WORD(string.digits) )

class ConfigVDevName(Grammar):
    grammar = ( OR('raidz1', 'raidz2', 'raidz3', 'mirror', 'spare'), '-', WORD(string.digits) )

class ConfigVDevState(Grammar):
    grammar = ( OR('ONLINE', 'DEGRADED', 'FAULTED', 'OFFLINE', 'UNAVAIL', 'REMOVED',), )

class ConfigDiskName(Grammar):
    grammar = ( WORD(string.ascii_letters + string.digits + "/") )

class ConfigPoolName(Grammar):
    grammar = ( WORD(string.ascii_letters + string.digits) )

class ConfigVDev(Grammar):
    grammar = ( ConfigVDevName, SpaceSeperator, ConfigVDevState, SpaceSeperator, ConfigCounters, )

class ConfigDiskStatusText(Grammar):
    grammar = ( REPEAT(SpaceSeperator, WORD(string.ascii_letters + string.punctuation + string.digits)), )

class ConfigDisk(Grammar):
    grammar = ( ConfigDiskName, SpaceSeperator, ConfigVDevState, SpaceSeperator, ConfigCounters, OPTIONAL(ConfigDiskStatusText), )

class ConfigSpareState(Grammar):
    grammar = ( OR('AVAIL', 'INUSE'), SpaceSeperator, OPTIONAL(REPEAT(SpaceSeperator, WORD(string.ascii_letters))), )

class ConfigSpareDisk(Grammar):
    grammar = ( ConfigDiskName, SpaceSeperator, ConfigSpareState, )

class ConfigHeader(Grammar):
    grammar = ( '\tNAME', SpaceSeperator, 'STATE     READ WRITE CKSUM\n', )

class ConfigPool(Grammar):
    grammar = ( ConfigPoolName, SpaceSeperator, ConfigVDevState, SpaceSeperator, ConfigCounters, '\n', REPEAT('\t', SpaceSeperator, OR(ConfigVDev, ConfigDisk), '\n'), )

class CacheDevices(Grammar):
    grammar = ( '\tcache\n', REPEAT('\t', SpaceSeperator, OR(ConfigVDev, ConfigDisk), '\n'), )

class SpareDevices(Grammar):
    grammar = ( '\tspares\n', REPEAT('\t', SpaceSeperator, ConfigSpareDisk, '\n'), )

class LogDevices(Grammar):
    grammar = ( '\tlogs\n', REPEAT('\t', SpaceSeperator, OR(ConfigVDev, ConfigDisk), '\n'), )

class ConfigBody(Grammar):
    grammar = ( '\t', ConfigPool, OPTIONAL(LogDevices), OPTIONAL(SpareDevices), OPTIONAL(CacheDevices), )

class ConfigField(Grammar):
    grammar = ( 'config:\n\n', ConfigHeader, ConfigBody, '\n' )

class SeeField(Grammar):
    grammar = ( '   see: ', FullFieldValue, )

class ScanField(Grammar):
    grammar = ( '  scan: ', FullFieldValue, )

class ActionField(Grammar):
    grammar = ( 'action: ', FullFieldValue, )

class StatusField(Grammar):
    grammar = ( 'status: ', FullFieldValue, )

class StateField(Grammar):
    grammar = ( ' state: ', FullFieldValue, )

class PoolNameField(Grammar):
    grammar = ( '  pool: ', FullFieldValue, )

class ZpoolStatus(Grammar):
    grammar = ( PoolNameField, StateField, StatusField, ActionField, ScanField, OPTIONAL(SeeField), ConfigField, ErrorsField, )

class LanguageOfZpoolStatuses(Grammar):
    grammar = ( REPEAT(ZpoolStatus, OPTIONAL(WORD('\n'))), )

# try:
#     p = ConfigField.parser()
#     with open('/tmp/zpool-config2', 'r') as fh:
#         configdata = fh.read()
#     r = p.parse_string(configdata, eof=True)
#     if r:
#         print 'parse success'
#         print r.elements
# except modgrammar.ParseError, e:
#     print 'parse error'
#     print e.message, 'at line', e.line, 'col', e.col
#
print '\n'.join(modgrammar.generate_ebnf(LanguageOfZpoolStatuses))


# statusfield = "status: Some supported features are not enabled on the pool. The pool can\n\
# still be used, but some features are unavailable."
#
# p = StatusField.parser()
# r = p.parse_string(statusfield, eof=True)
# if r:
#     print 'parse succeeded'
#     print repr(r)
# else:
#     print 'parse failed'

# bigfield = """something something\n
#         watttttttt wat"""
#
# p = FullFieldValue.parser()
# r = p.parse_string(bigfield, eof=True)
# print r
#
# fieldword = "whatwhat"
# p = FieldWord.parser()
# r = p.parse_string(fieldword, eof=True)
# print r

# print '\n'.join(modgrammar.generate_ebnf(LanguageOfZpoolStatuses))

# p = LanguageOfZpoolStatuses.parser()
#
# try:
#     with open('/tmp/zpool-status', 'r') as fh:
#     with open('/tmp/zpool-status-testpool', 'r') as fh:
#     with open('/tmp/zpool-one-status', 'r') as fh:
        # testdata = fh.read()
    # r = p.parse_string(testdata, eof=True)
    # print repr(r)
    # if r:
    #     for t in r.terminals():
    #         print repr(t)
    #
    #     for pool in r.find_all(ConfigPool):
    #         print repr(pool)
        # print r,
        # print '====remainder==='
        # print p.remainder(),
        # print '======'
    # IPython.embed()
# except modgrammar.ParseError, e:
#     print e.message
#     print e.line
#     print e.col
#     print e.expected
#
#
# simpledata = "  pool: rpool\n"
# print simpledata
#
# p = PoolNameField.parser()
# try:
#     r = p.parse_string(simpledata, eof=True)
#     if r:
#         print dir(r)
# except modgrammar.ParseError, e:
#     print e.message
#     print e.line
#     print e.col
#     print e.expected
