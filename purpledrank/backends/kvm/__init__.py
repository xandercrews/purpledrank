__author__ = 'achmed'

from .. import backendutil

import os

import json
import glob

import collections

import logging
logger = logging.getLogger(__name__)

# treat each machine inventory separately or assume they are shared?
#     the difference is whether or not to lock inventory files when they are being
#     modified
#

# can update inventory state on events with inotify (but it doesn't work on NFS)

class KVMInventoryInterface(object):
    VM_FILE_SUFFIX = '.vm.json'

    def __init__(self, inventorydir='/kvm'):
        self.inventorydir = inventorydir
        if not os.path.isdir(inventorydir):
            raise Exception('invalid inventory directory')

    # check for existence of vm by name
    def isVm(self, name):
        vmpath = self._resolveVmPath(name)
        if not os.path.isfile(vmpath):
            return False

        with open(vmpath, 'r') as fd:
            d = json.load(fd)
            self._validateVm(name, d)

        return True

    # list vms
    def listVms(self):
        vms = []

        for filename in glob.glob(os.path.join(self.inventorydir, '*%s' % self.VM_FILE_SUFFIX)):
            vmname = os.path.basename(filename).split(self.VM_FILE_SUFFIX)[0]

            with open(filename, 'r') as fd:
                d = json.load(fd)
                self._validateVm(vmname, d)

            vms.append(vmname)

        return vms

    # create a new vm based on a descriptor
    def createVm(self, vm):
        if isinstance(vm, collections.Mapping):
           pass
        elif isinstance(vm, (basestring, unicode)):
            vm = json.loads(vm)

        self._validateVm(vm)

        vmname = vm['name']

        assert len(vmname) > 0

        vmpath = self._resolveVmPath(vmname)

        try:
            with open(vmpath, os.O_CREAT) as fd:
                json.dump(vm, fd)
        except IOError, e:
            print e
            print dir(e)
            raise

        return vmname

    def _validateVm(self, vm, name=None):
        try:
            if name is not None:
                assert vm['name'] == name, 'name in file does not match expected name'

            assert 'vcpu' in vm, 'vcpu field missing'
            assert isinstance(vm['vcpu'], int), 'vcpu must be integer'
            assert 1 <= vm['vcpu'] <= 64, 'vcpu value invalid (1<=vcpu<=64)'

            assert 'memory' in vm, 'memory field missing'
            assert isinstance(vm['memory'], int), 'vcpu must be integer'
            assert 1 <= vm['memory'] <= 512 * 1024

            assert 'display' in vm, 'display field missing'
            assert 'vnc' in vm['display'] or 'spice' in vm['display'], 'at least one of vnc or spice must be specified'
        except Exception, e:
            raise Exception('invalid vm: %s' % e.message)

        return True

    def _resolveVmPath(self, name):
        return os.path.join(self.inventorydir, '%s%s' % (name, self.VM_FILE_SUFFIX,))


class KVMControlInterface(object):
    def __init__(self, inventory, piddir):
        self.inventory = inventory

    # start or stop a kvm virtual machine by name
    def start(self, vmname):
        pass

    def stop(self, vmname):
        pass
