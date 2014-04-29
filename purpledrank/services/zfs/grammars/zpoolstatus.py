__author__ = 'achmed'

grammar_whitespace = False

from modgrammar import Grammar, REPEAT, WORD, OPTIONAL, L, OR
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
