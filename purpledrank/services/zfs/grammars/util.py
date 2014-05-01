__author__ = 'achmed'

import sys
import modgrammar
import zpoolstatus as zg
import string

def terminals_to_str(grammar, add_whitespace=False):
    spacing = ''
    if add_whitespace:
        spacing = ' '
    return spacing.join(map(str, grammar.terminals()))

def trim_full_field(s):
    return s.translate(string.maketrans('\n',' '), '\t').strip()

def get_device_tree(g):
    device_tree = {}
    prev_spacing = 0
    for p in g.find_all(zg.ZpoolStatus):
        pool_name = terminals_to_str(p.find(zg.PoolNameField).get(zg.FullFieldValue)).strip()
        d = device_tree[pool_name] = dict(name=pool_name)

        # status
        try:
            pool_status = terminals_to_str(p.find(zg.StatusField).get(zg.FullFieldValue))
            d['status'] = trim_full_field(pool_status)
        except Exception, e:
            d['status'] = None

        # state
        try:
            pool_state = terminals_to_str(p.find(zg.StateField).get(zg.FullFieldValue))
            d['state'] = trim_full_field(pool_state)
        except Exception, e:
            d['state'] = None

        # action
        try:
            pool_action = terminals_to_str(p.find(zg.ActionField).get(zg.FullFieldValue))
            d['action'] = trim_full_field(pool_action)
        except Exception, e:
            d['action'] = None

        # scan
        try:
            pool_scan = terminals_to_str(p.find(zg.ScanField).get(zg.FullFieldValue))
            d['scan'] = trim_full_field(pool_scan)
        except Exception, e:
            d['scan'] = None

        # see
        try:
            pool_see = terminals_to_str(p.find(zg.SeeField).get(zg.FullFieldValue))
            d['see'] = trim_full_field(pool_see)
        except Exception, e:
            d['see'] = None

        # errors
        try:
            pool_errors = terminals_to_str(p.find(zg.ErrorsField).get(zg.FullFieldValue))
            d['errors'] = trim_full_field(pool_errors)
        except Exception, e:
            d['errors'] = None

        # config
        for d in p.find(zg.ConfigBody).get(zg.ConfigPool).find_all(zg.ConfigDevice):
            spacing = d.find_all(zg.ConfigDeviceSpacing)
            assert len(spacing) == 1, 'expected only one spacing production per device in config'
            spacing = len(spacing[0])

            for e in d.elements:
                if e is not None:
                    print e.__class__
                else:
                    print 'None'

            prev_spacing = spacing

    return device_tree

def print_parse_tree_types(g, level=0, exclude=('FieldWord', 'SpaceSeparator')):
    '''
    :type g: modgrammar.Grammar
    '''
    for e in g.elements:
        if e is not None:
            if not e.grammar_collapse and str(e.__class__) in dir(zg) and str(e.__class__) not in exclude:
                sys.stdout.write('  ' * level)
                print e.__class__
                print_parse_tree_types(e, level+1)
            else:
                print_parse_tree_types(e, level)

if __name__ == "__main__":
    import modgrammar
    import pprint
    p = zg.LanguageOfZpoolStatuses.parser()
    with open('/tmp/zpool-status', 'r') as fh:
        testdata = fh.read()
    try:
        g = p.parse_string(testdata, eof=True)
        assert g is not None
        print p.remainder()
        get_device_tree(g)
        pprint.pprint(get_device_tree(g), indent=2)
        # print_parse_tree_types(g)
    except modgrammar.ParseError, e:
        print e.message, 'line', e.line, 'col', e.col
