__author__ = 'achmed'

import jsonpatch
import copy
import collections

def dictequal(d1, d2):
    '''
    compares two unordered dicts for equality in a fairly expensive way
    '''
    p = jsonpatch.make_patch(d1, d2)
    return len(p.patch) == 0

def update_r(d, *us):
    '''
    returns a new dictionary with the merged contents of all arguments
    '''
    newd = copy.deepcopy(d)
    if newd is None:
        newd = {}
    for u in us:
        for k, v in u.iteritems():
            if isinstance(v, collections.Mapping):
                r = update_r(newd.get(k, {}), v)
                newd[k] = r
            else:
                newd[k] = u[k]
    return newd
