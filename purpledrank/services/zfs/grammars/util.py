__author__ = 'achmed'

import sys
import modgrammar
import zpoolstatus

def get_device_tree(g):
    device_tree = {}
    for p in g.find_all(zpoolstatus.ZpoolStatus):
        pool_name = ''.join(map(str,p.find_all(zpoolstatus.PoolNameField)[0].elements[1].elements[0].terminals())).strip()
        for d in p.find_all(zpoolstatus.ConfigDevice):
            spacing = d.find_all(zpoolstatus.ConfigDeviceSpacing)
            assert len(spacing) == 1, 'expected only one spacing production per device in config'
            spacing = len(spacing[0])
            print spacing
        device_tree[pool_name] = {}
    return device_tree

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
    import pprint
    p = zpoolstatus.LanguageOfZpoolStatuses.parser()
    with open('/tmp/zpool-status', 'r') as fh:
        testdata = fh.read()
    try:
        g = p.parse_string(testdata, eof=True)
        assert g is not None
        print p.remainder()
        # print_parse_tree_types(g)
        pprint.pprint(get_device_tree(g), indent=2)
    except modgrammar.ParseError, e:
        print e.message, 'line', e.line, 'col', e.col
