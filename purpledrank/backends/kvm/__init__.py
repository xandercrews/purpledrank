__author__ = 'achmed'

from contextlib import closing

from .. import backendutil

import os

import json
import glob

import collections

import subprocess

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
            self._validateVm(d, name)

        return True

    # list vms
    def listVms(self):
        vms = []

        for filename in glob.glob(os.path.join(self.inventorydir, '*%s' % self.VM_FILE_SUFFIX)):
            vmname = os.path.basename(filename).split(self.VM_FILE_SUFFIX)[0]

            with open(filename, 'r') as fd:
                d = json.load(fd)
                self._validateVm(d, vmname)

            vms.append(vmname)

        return vms

    def getVm(self, name):
        vmpath = self._resolveVmPath(name)

        with open(vmpath, 'r') as fd:
            d = json.load(fd)
            self._validateVm(d)

        return d

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

        fd = os.open(vmpath, os.O_CREAT|os.O_WRONLY|os.O_EXCL)
        with closing(os.fdopen(fd, 'w')) as f:
            json.dump(vm, f, indent=2)

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
    KVM_COMMAND_LINE = "/usr/bin/kvm"

    def __init__(self, inventory, piddir='/var/run/kvm'):
        self.inventory = inventory

    # start or stop a kvm virtual machine by name
    def start(self, vmname):
        vm = self.inventory.getVm(vmname)

        if vm is None:
            raise Exception('vm \'%s\' does not exist' % vmname)

        cmdlines = self._vmToCommandLine(vm)

        p = subprocess.Popen([ self.KVM_COMMAND_LINE ] + cmdlines, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
        out,err = p.communicate()

        if p.returncode != 0:
            raise Exception('failed to create vm \'%s\': %s' % (vmname, str(err)))

        cmdlines = self._vmToCommandLine(vm)

        p = subprocess.Popen([ self.KVM_COMMAND_LINE ] + cmdlines, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
        out,err = p.communicate()

        if p.returncode != 0:
            raise Exception('failed to start vm: %s' % err)

    def stop(self, vmname):
        pass

    def _vmToCommandLine(self, vm):
        cmdlines = []

        # vm name
        cmdlines += [ "-name", "%s" % vm['name'] ]

        # cpu mem
        cmdlines += [ "-smp", "%d" % vm['vcpu'] ]
        cmdlines += [ "-memory", "%d" % vm['memory'] ]

        # nic stuff
        if 'nics' in vm:
            for nic in vm['nics']:
                pass

        # disk stuff
        if 'disks' in vm:
            for disk in vm['disks']:
                pass

        # spice display
        if 'spice' in vm['display']:
            spice = vm['display']['spice']
            spiceline = 'port=%d' % spice['port']
            if 'disable-ticketing' in spice and spice['disable-ticketing']:
                spiceline += ',disable-ticketing'
            cmdlines += [ '-spice', spiceline ]
            cmdlines += [ '-vga', 'qxl' ]

        # vnc display
        if 'vnc' in vm['display']:
            vnc = vm['display']['vnc']
            assert 5900 <= vnc['port'] <= 65535
            cmdlines += [ '-vnc', ':%d' % (vnc['port'] - 5900) ]

        # standard stuff
        cmdlines += [ "-daemonize" ]
        cmdlines += [ "-usbdevice", "tablet" ]

        return cmdlines
