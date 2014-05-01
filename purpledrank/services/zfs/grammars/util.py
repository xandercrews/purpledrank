__author__ = 'achmed'

import sys
import modgrammar
import zpoolstatus

def print_parse_tree_types(g, level=0, exclude=('FieldWord', 'SpaceSeparator')):
    '''
    :type g: modgrammar.Grammar
    '''
    for e in g.elements:
        if e is not None:
            if not e.grammar_collapse and str(e.__class__) in dir(zpoolstatus) and str(e.__class__) not in exclude:
                sys.stdout.write('  ' * level)
                print e.__class__
                print_parse_tree_types(e, level+1)
            else:
                print_parse_tree_types(e, level)

if __name__ == "__main__":
    import zpoolstatus
    import modgrammar
    p = zpoolstatus.LanguageOfZpoolStatuses.parser()
    with open('/tmp/zpool-status', 'r') as fh:
        testdata = fh.read()
    try:
        g = p.parse_string(testdata, eof=True)
        assert g is not None
        print_parse_tree_types(g)
    except modgrammar.ParseError, e:
        print e.message, 'line', e.line, 'col', e.col
