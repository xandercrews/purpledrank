__author__ = 'achmed'

def scan_iter(rconn, match=None, count=None):
    """
    Make an iterator using the SCAN command so that the client doesn't
    need to remember the cursor position.

    ``match`` allows for filtering the keys by pattern

    ``count`` allows for hint the minimum number of returns
    """
    cursor = 0
    while cursor != '0':
        cursor, data = rconn.scan(cursor=cursor, match=match, count=count)
        for item in data:
            yield item

def make_prefix(*components):
    '''
    make a prefix for keys based on components.
    for now, check that no colons exist in the inputs and
    concatenate with a colon
    '''
    for c in components:
        assert '\0' not in c, 'null (\\0) not allowed in key prefix component'

    return '\0'.join(components)

def add_prefix(prefix, *components):
    '''
    add a prefix to key components
    for now just  make sure the key components don't already
    and combine that prefix with a colon
    '''
    return prefix + '\0' + make_prefix(*components)