__author__ = 'achmed'

grammar_whitespace = False

from modgrammar import Grammar, REPEAT, WORD, OPTIONAL, L, OR
import string

class SpaceSeparator(Grammar):
    grammar_greedy = True
    grammar = ( WORD(' '), )

class FieldWord(Grammar):
    grammar = ( WORD(string.ascii_letters + string.digits + string.punctuation) )

class FirstFieldValue(Grammar):
    grammar = ( FieldWord, OPTIONAL(REPEAT(SpaceSeparator, FieldWord)), L('\n'), )

class IndentedFieldValue(Grammar):
    grammar = ( OR('        ', '\t'), FirstFieldValue, )

class FullFieldValue(Grammar):
    grammar = ( FirstFieldValue, OPTIONAL(REPEAT(IndentedFieldValue)), )

class ErrorsField(Grammar):
    grammar = ( 'errors: ', FullFieldValue, )

class ConfigCounters(Grammar):
    grammar = ( WORD(string.digits), SpaceSeparator, WORD(string.digits), SpaceSeparator, WORD(string.digits) )

class ConfigVDevName(Grammar):
    grammar = ( OR('raidz1', 'raidz2', 'raidz3', 'mirror', 'spare'), '-', WORD(string.digits) )

class ConfigVDevState(Grammar):
    grammar = ( OR('ONLINE', 'DEGRADED', 'FAULTED', 'OFFLINE', 'UNAVAIL', 'REMOVED',), )

class ConfigDiskName(Grammar):
    grammar = ( WORD(string.ascii_letters + string.digits + "/") )

class ConfigPoolName(Grammar):
    grammar = ( WORD(string.ascii_letters + string.digits) )

class ConfigDeviceSpacing(Grammar):
    grammar = ( '\t', SpaceSeparator, )

class ConfigVDev(Grammar):
    grammar = ( ConfigDeviceSpacing, ConfigVDevName, SpaceSeparator, ConfigVDevState, SpaceSeparator, ConfigCounters, '\n' )

class ConfigDiskStatusText(Grammar):
    grammar = ( REPEAT(SpaceSeparator, WORD(string.ascii_letters + string.punctuation + string.digits)), )

class ConfigDisk(Grammar):
    grammar = ( ConfigDeviceSpacing, ConfigDiskName, SpaceSeparator, ConfigVDevState, SpaceSeparator, ConfigCounters, OPTIONAL(ConfigDiskStatusText), '\n' )

class ConfigSpareState(Grammar):
    grammar = ( OR('AVAIL', 'INUSE'), SpaceSeparator, OPTIONAL(REPEAT(SpaceSeparator, WORD(string.ascii_letters))), )

class ConfigSpareDisk(Grammar):
    grammar = ( ConfigDiskName, SpaceSeparator, ConfigSpareState, )

class ConfigHeader(Grammar):
    grammar = ( '\tNAME', SpaceSeparator, 'STATE     READ WRITE CKSUM\n', )

class ConfigDevice(Grammar):
    grammar = ( OR(ConfigVDev, ConfigDisk), )

class ConfigPool(Grammar):
    grammar = ( ConfigPoolName, SpaceSeparator, ConfigVDevState, SpaceSeparator, ConfigCounters, '\n', REPEAT(ConfigDevice), )

class CacheDevices(Grammar):
    grammar = ( '\tcache\n', REPEAT('\t', SpaceSeparator, OR(ConfigVDev, ConfigDisk), '\n'), )

class SpareDevices(Grammar):
    grammar = ( '\tspares\n', REPEAT('\t', SpaceSeparator, ConfigSpareDisk, '\n'), )

class LogDevices(Grammar):
    grammar = ( '\tlogs\n', REPEAT('\t', SpaceSeparator, OR(ConfigVDev, ConfigDisk), '\n'), )

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
