from purpledrank.backends.zfs.grammars import zpoolstatus as zg

__author__ = 'achmed'

import sys
import string

import subprocess

def terminals_to_str(grammar, add_whitespace=False):
    spacing = ''
    if add_whitespace:
        spacing = ' '
    return spacing.join(map(str, grammar.terminals()))

def trim_full_field(s):
    return s.translate(string.maketrans('\n',' '), '\t').strip()

def get_config_device_tree(rootdevice, grammars, disktype=zg.ConfigDisk, vdevtype=zg.ConfigVDev, statetype=zg.ConfigDevState):
    # pool devices
    prev_spacing = -1
    current_device = rootdevice
    device_stack = [ rootdevice ]

    dev = None

    for cdev in grammars:
        spacing = len(cdev.find(zg.ConfigDeviceSpacing))

        if disktype == zg.ConfigDisk:
            cdev = cdev.elements[0]

        if prev_spacing >= 0:
            if spacing > prev_spacing:
                device_stack.append(current_device)
                current_device = dev
            elif spacing < prev_spacing:
                current_device = device_stack.pop()

        assert len(device_stack) > 0, 'device stack must not become empty'

        if cdev.__class__ == disktype:
            # disk
            if 'disks' not in current_device:
                current_device['disks'] = []

            disk_name = terminals_to_str(cdev.find(zg.ConfigDiskName))
            disk_state = terminals_to_str(cdev.find(statetype)).strip()

            # TODO errors

            dev = dict(name=disk_name, state=disk_state)
            current_device['disks'].append(dev)
        else:
            # vdev
            assert cdev.__class__ == vdevtype, 'assumed non-disk device is vdev'
            if 'vdevs' not in current_device:
                current_device['vdevs'] = []

            vdev_name = terminals_to_str(cdev.find(zg.ConfigVDevName))
            vdev_state = terminals_to_str(cdev.find(zg.ConfigDevState)).strip()

            # TODO errors

            dev = dict(name=vdev_name, state=vdev_state)
            current_device['vdevs'].append(dev)

        prev_spacing = spacing

def get_zpool_tree(g):
    device_tree = {}
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

        # pool devices
        get_config_device_tree(d, p.find_all(zg.ConfigDevice))

        # pool cache devs
        d['cache'] = {}
        cachedevs = p.find(zg.CacheDevices)
        if cachedevs is not None:
            get_config_device_tree(d['cache'], cachedevs.find_all(zg.ConfigDevice))

        # pool log devs
        d['logs'] = {}
        logdevs = p.find(zg.LogDevices)
        if logdevs is not None:
            logconfigdevs = logdevs.find_all(zg.ConfigDevice)
            get_config_device_tree(d['logs'], logconfigdevs)

        # pool spare devs
        d['spares'] = {}
        sparedevs = p.find(zg.SpareDevices)
        if sparedevs is not None:
            get_config_device_tree(d['spares'], sparedevs.find_all(zg.ConfigSpareDisk), disktype=zg.ConfigSpareDisk, statetype=zg.ConfigSpareState)

    return device_tree

def print_parse_tree_types(g, level=0, exclude=('FieldWord', 'SpaceSeparator')):
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
    with open('/tmp/zpool-status-remainder', 'r') as fh:
        testdata = fh.read()
    try:
        g = p.parse_string(testdata, eof=True)
        assert g is not None
        # assert len(p.remainder()) == 0
        # print p.remainder()
        # get_zpool_tree(g)
        pprint.pprint(get_zpool_tree(g), indent=2)
        # print_parse_tree_types(g)
    except modgrammar.ParseError, e:
        print e.message, 'line', e.line, 'col', e.col

def _generic_command(cmd, *args):
    p = subprocess.Popen([cmd] + list(args), stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    rc = p.returncode

    if rc != 0:
        raise Exception('%s failed: %s' % (cmd, stderr,))

    return stdout
