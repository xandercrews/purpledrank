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

grammar_whitespace = False

from modgrammar import Grammar, REPEAT, WORD, OPTIONAL, L, LITERAL
import modgrammar
import string

class FieldToken(Grammar):
    # grammar_whitespace = False
    grammar = ( WORD(string.ascii_letters + string.digits + string.punctuation) )

class FirstFieldValue(Grammar):
    # grammar_whitespace = False
    grammar = ( FieldToken, OPTIONAL(REPEAT(WORD(string.whitespace), FieldToken)), '\n', )

class IndentedFieldValue(Grammar):
    # grammar_whitespace = False
    grammar = ( '        ', FirstFieldValue, )

class FullFieldValue(Grammar):
    # grammar_whitespace = False
    grammar = ( FirstFieldValue, OPTIONAL(REPEAT(IndentedFieldValue)), )

class ErrorsField(Grammar):
    # grammar_whitespace = False
    grammar = ( 'errors: ', FullFieldValue, )

class ConfigField(Grammar):
    # grammar_whitespace = False
    grammar = ( 'config: ', FullFieldValue, )

class ScanField(Grammar):
    # grammar_whitespace = False
    grammar = ( '  scan: ', FullFieldValue, )

class ActionField(Grammar):
    # grammar_whitespace = False
    grammar = ( 'action: ', FullFieldValue, )

class StatusField(Grammar):
    # grammar_whitespace = False
    grammar = ( 'status: ', FullFieldValue, )

class StateField(Grammar):
    # grammar_whitespace = False
    grammar = ( ' state: ', FullFieldValue, )

class PoolNameField(Grammar):
    # grammar_whitespace = False
    grammar = ( '  pool: ', FullFieldValue, )

class ZpoolStatus(Grammar):
    # grammar_whitespace = False
    grammar = ( PoolNameField, StateField, StatusField, ActionField, ScanField, ConfigField, ErrorsField, )

class LanguageOfZpoolStatus(Grammar):
    # grammar_whitespace = False
    grammar = ( REPEAT(ZpoolStatus), )

p = LanguageOfZpoolStatus.parser()
# print '\n'.join(modgrammar.generate_ebnf(LanguageOfZpoolStatus))
try:
    r = p.parse_string(testdata, eof=True)
    if r:
        print r.tokens()
except modgrammar.ParseError, e:
    print e.message
    print e.line
    print e.col
    print e.expected
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
