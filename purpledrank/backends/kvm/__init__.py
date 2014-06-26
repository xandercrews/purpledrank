__author__ = 'achmed'

from contextlib import closing

import os
import stat

import json
import glob

import collections

import subprocess

from ...thirdparty import qmp

from ...errors import VMValidationError

from contextlib import contextmanager

import tempfile

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
    def is_vm(self, name):
        vmpath = self._resolve_vm_path(name)
        if not os.path.isfile(vmpath):
            return False

        with open(vmpath, 'r') as fd:
            d = json.load(fd)
            self._validate_vm(d, name)

        return True

    # list vms
    def list_vms(self):
        vms = []

        for filename, vmname in self._iter_vm_files():
            try:
                with open(filename, 'r') as fd:
                    d = json.load(fd)
                    self._validate_vm(d, vmname)

                    vms.append(vmname)

            except VMValidationError, e:
                logger.warn('invalid vm (%s) configuration: %s' % (vmname, e.message))

        return vms

    def list_invalid_vmfiles(self):
        invalid_vms = []

        for filename, vmname in self._iter_vm_files():
            try:
                with open(filename, 'r') as fd:
                    d = json.load(fd)
                    self._validate_vm(d, vmname)

            except VMValidationError, e:
                invalid_vms.append((vmname, e.message,))

        return invalid_vms

    def get_vm(self, name):
        vmpath = self._resolve_vm_path(name)

        with open(vmpath, 'r') as fd:
            d = json.load(fd)
            self._validate_vm(d)

        return d

    # create a new vm based on a descriptor
    def create_vm(self, vm):
        if isinstance(vm, collections.Mapping):
           pass
        elif isinstance(vm, (basestring, unicode)):
            vm = json.loads(vm)

        self._validate_vm(vm)

        vmname = vm['name']

        assert len(vmname) > 0

        vmpath = self._resolve_vm_path(vmname)

        fd = os.open(vmpath, os.O_CREAT|os.O_WRONLY|os.O_EXCL)
        with closing(os.fdopen(fd, 'w')) as f:
            json.dump(vm, f, indent=2)

        return vmname

    def _validate_vm(self, vm, name=None):
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

            if 'vnc' in vm['display']:
                vnc = vm['display']['vnc']
                assert 'port' in vnc, 'vnc port missing'
            else:
                assert 'spice' in vm['display'], 'at least one of vnc or spice must be specified'
                spice = vm['display']['spice']
                assert 'port' in spice

            assert 'qmp-port' in vm, 'qmp field missing'
            assert isinstance(vm['qmp-port'], int), 'qmp port must be an integer'
            assert 1024 < vm['qmp-port'] <= 65535, 'invalid qmp port'

            if 'disks' in vm:
                for disk in vm['disks']:
                    assert 'file' in disk or 'lun' in disk, 'file or lun option required in disk'
                    assert 'interface' not in disk or disk['interface'] in ('virtio', 'ide', 'scsi', 'floppy', 'sd', 'mtd', 'pflash',), 'invalid disk interface type'
                    assert 'cache' not in disk or disk['cache'] in ('none', 'writeback', 'writethrough',), 'invalid cache option in disk'
                    assert 'format' not in disk or disk['format'] in ('qcow2', 'host_device', 'raw', 'qcow', 'cow', 'vdi', 'vmdk', 'vpc', 'cloop')

            if 'nics' in vm:
                for nic in vm['nics']:
                    assert 'type' in nic and nic['type'] in ('vhost', 'tap',), 'invalid nic type'
                    assert 'macaddr' in nic, 'missing macaddr'
                    assert ( 'trunk' in nic and nic['trunk'] ) or 'access-vlan' in nic and isinstance(nic['access-vlan'], int), 'need one of trunk or access vlan'
                    assert 'model' in nic and nic['model'] in ('e1000', 'virtio',), 'missing nic model'

        except AssertionError, e:
            raise VMValidationError('vm: %s' % e.message)

        return True

    def _resolve_vm_path(self, name):
        return os.path.join(self.inventorydir, '%s%s' % (name, self.VM_FILE_SUFFIX,))

    def _iter_vm_files(self):
        for filename in glob.glob(os.path.join(self.inventorydir, '*%s' % self.VM_FILE_SUFFIX)):
            vmname = os.path.basename(filename).split(self.VM_FILE_SUFFIX)[0]
            yield filename, vmname


class KVMCommandInterface(object):
    KVM_COMMAND_LINE = "/usr/bin/kvm"

    def __init__(self, inventory, piddir='/var/run/kvm'):
        self.inventory = inventory
        self.piddir = piddir

    # start a vm by name
    def start(self, vmname):
        # TODO prevent race where a vm could be started in between checks-
        # qemu provides a pidfile option but does not check it and start
        # the VM atomically
        if self._vm_is_running(vmname):
            raise Exception('vm is running')

        vm = self.inventory.get_vm(vmname)

        if vm is None:
            raise Exception('vm \'%s\' does not exist' % vmname)

        cmdline = self._vm_to_cmdline(vm)

        cmdline = [self.KVM_COMMAND_LINE] + cmdline

        logger.debug('executing kvm command: %s' % ' '.join(cmdline))
        print ' '.join(cmdline)

        p = subprocess.Popen(cmdline, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()

        if p.returncode != 0:
            raise Exception('could not start vm: %s' % err)

        # verify vm is running via qmp interface
        with self._get_mon(vm) as mon:
            resp = mon.command('query-status')
            logger.debug('monitor response: %s' % resp)

    # start a vm in incoming mode
    def start_migrate_target(self, vmname, migrateport):
        # TODO prevent race where a vm could be started in between checks-
        # qemu provides a pidfile option but does not check it and start
        # the VM atomically
        try:
            migrateport = int(migrateport)
        except ValueError:
            raise Exception('migrate port must be a number')

        assert 1024 < migrateport < 65536, 'migration port should be a non-privileged port num'

        if self._vm_is_running(vmname):
            raise Exception('vm is running')

        vm = self.inventory.get_vm(vmname)

        if vm is None:
            raise Exception('vm \'%s\' does not exist' % vmname)

        cmdline = self._vm_to_cmdline(vm)

        # TODO make
        cmdline = [self.KVM_COMMAND_LINE] + cmdline + ['-incoming', 'tcp:0.0.0.0:%d' % migrateport]

        logger.debug('executing kvm command: %s' % ' '.join(cmdline))
        print ' '.join(cmdline)

        p = subprocess.Popen(cmdline, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()

        if p.returncode != 0:
            raise Exception('could not start vm: %s' % err)

        # verify vm is running via qmp interface
        with self._get_mon(vm) as mon:
            resp = mon.command('query-status')
            logger.debug('monitor response: %s' % resp)

        return migrateport

    # begin migration to a remote target in incoming mode
    def migrate(self, vmname, target, speedinkb=None, downtimeinseconds=None):
        vm = self.inventory.get_vm(vmname)

        if vm is None:
            raise Exception('vm \'%s\' does not exist')

        if not self._vm_is_running(vmname):
            raise Exception('vm is not running')

        args = {'uri': 'tcp:%s' % target}

        if speedinkb is not None:
            try:
                speedinkb = int(speedinkb)
            except ValueError:
                raise Exception('migration speed must be specified numerically in kb')
        else:
            speedinkb = 1600 * 1024    # theoretical DDR IB limit

        if downtimeinseconds is not None:
            try:
                downtimeinseconds = float(downtimeinseconds)
            except ValueError:
                raise Exception('downtime must be specified numerically in seconds')

        with self._get_mon(vm) as mon:
            resp = mon.command('migrate_set_speed', value=speedinkb)
            logger.debug('migrate set speed (%d) response: %s' % (speedinkb, resp))

            if downtimeinseconds is not None:
                resp = mon.command('migrate_set_downtime', value=float(downtimeinseconds))
                logger.debug('migrate set downtime (%f) response: %s' % (downtimeinseconds, resp))

            resp = mon.command('migrate', **args)
            logger.debug('migrate response: %s' % resp)

        return resp

    def shutdown(self, vmname):
        vm = self.inventory.get_vm(vmname)

        with self._get_mon(vm) as mon:
            resp = mon.command('system_powerdown')
            logger.debug('monitor response: %s' % resp)

    def kill(self, vmname):
        vm = self.inventory.get_vm(vmname)

        with self._get_mon(vm) as mon:
            resp = mon.command('quit')
            logger.debug('monitor response: %s' % resp)

    def zap(self, vmname):
        try:
            os.unlink(self._vm_pidfile(vmname))
        except IOError:
            pass

    def mon_command(self, vmname, command, *args):
        vm = self.inventory.get_vm(vmname)

        kwargs =dict(map(lambda a: a.split('=', 1), args))

        with self._get_mon(vm) as mon:
            resp = mon.command(command, **kwargs)
            logger.debug('monitor response: %s' % resp)

        return resp

    def vm_info(self, vmname):
        vm = self.inventory.get_vm(vmname)

        running = self._vm_is_running(vmname)

        if running:
            with self._get_mon(vm) as mon:
                blockdev = mon.command('query-block')
                blockstats = mon.command('query-blockstats')
                status = mon.command('query-status')
                vnc = mon.command('query-vnc')
                spice = mon.command('query-spice')
        else:
            blockdev = None
            blockstats = None
            status = None
            vnc = None
            spice = None

        return vm, running, dict(blockdev=blockdev, blockstats=blockstats, status=status, vnc=vnc, spice=spice)

    def set_spice_ticket(self, vmname, ticket, expiry):
        vm = self.inventory.get_vm(vmname)

        with self._get_mon(vm) as mon:
            mon.command('set_password', protocol='spice', password=ticket)
            mon.command('expire_password', protocol='spice', time=expiry)

    @contextmanager
    def _get_mon(self, vm):
        mon = qmp.QEMUMonitorProtocol(('127.0.0.1', vm['qmp-port'],))
        mon.connect()
        yield mon
        mon.close()

    def _vm_is_running(self, vmname):
        pidfile = self._vm_pidfile(vmname)

        try:
            with open(pidfile, 'r') as fh:
                vmpid = int(fh.read())
            if os.path.exists('/proc/%d/' % vmpid):
                return True
        except IOError:
            pass
        except ValueError:
            pass

        return False

    def _vm_pidfile(self, vmname):
        return os.path.join(self.piddir, '%s.pid' % vmname)

    def _vm_to_cmdline(self, vm):
        cmdline = []

        # vm name
        cmdline += [ "-name", "%s" % vm['name'] ]

        # cpu mem
        cmdline += [ "-smp", "%d" % vm['vcpu'] ]
        cmdline += [ "-m", "%d" % vm['memory'] ]

        # disk stuff
        if 'disks' in vm:
            for disk in vm['disks']:
                diskopts = []

                if 'file' in disk:
                    diskopts += [ 'file=%s' % disk['file'] ]
                elif 'lun' in disk:
                    diskopts += [ 'file=/dev/iscsi/%s' % disk['lun'] ]

                if 'interface' in disk:
                    diskopts += [ 'if=%s' % disk['interface'] ]

                if 'cache' in disk:
                    diskopts += [ 'cache=%s' % disk['cache'] ]

                if 'format' in disk:
                    diskopts += [ 'format=%s' % disk['format'] ]

                diskopts += [ 'aio=native' ]
                diskopts += [ 'werror=stop' ]
                diskopts += [ 'rerror=stop' ]

                cmdline += [ '-drive', ','.join(diskopts) ]

        nicdev = 1
        # nic stuff
        if 'nics' in vm:
            for nic in vm['nics']:
                assert 'type' in nic and nic['type'] in ('vhost', 'tap')
                assert 'macaddr' in nic
                assert ( 'trunk' in nic and nic['trunk'] ) or 'access-vlan' in nic and isinstance(nic['access-vlan'], int)
                assert 'model' in nic and nic['model'] in ('e1000', 'virtio')

                upscript = self._temp_script()
                downscript = self._temp_script()

                if 'trunk' in nic and nic['trunk']:
                    # why did i sleep in here?

                    # TOOD remove hardcoded bridge names
                    print >>upscript[0], \
"""#!/bin/sh
/usr/bin/ovs-vsctl del-port vmbr0 $1
/sbin/ifconfig $1 0 up
/usr/bin/ovs-vsctl add-port vmbr0 $1
sleep 5
/sbin/ifconfig $1 0 up
"""
                else:
                    assert 'access-vlan' in nic
                    print >>upscript[0], \
"""#!/bin/sh
/usr/bin/ovs-vsctl del-port vmbr0 $1
/sbin/ifconfig $1 0 up
/usr/bin/ovs-vsctl add-port vmbr0 $1 tag=%d
""" % nic['access-vlan']

                print >>downscript[0], """
                #!/bin/sh
                /sbin/ifconfig $1 0 down
                /usr/bin/ovs-vsctl del-port vmbr0 $1
                """

                upscript[0].close()
                downscript[0].close()

                if nic['type'] == 'vhost':
                    nicdevname = '%s.%d' % (vm['name'], nicdev)
                    cmdline += [ '-net', 'nic,macaddr=%s,model=%s,model=%s,netdev=%s' % (nic['macaddr'], nic['model'], nic['model'], nicdevname) ]
                    cmdline += [ '-netdev', 'tap,ifname=%s,id=%s,vhost=on,script=%s,downscript=%s,' % (nicdevname, nicdevname, upscript[1], downscript[1])]

                else:
                    assert nic['type'] == 'tap'
                    cmdline += ['-net', 'nic,macaddr=%s,model=%s,vlan=%d' % (nic['macaddr'], nic['model'], nicdev)]
                    cmdline += [ '-net', 'tap,vlan=%d,script=%s,downscript=%s' % (nicdev, upscript[1], downscript[1])]

                nicdev += 1

        # spice display
        if 'spice' in vm['display']:
            spice = vm['display']['spice']
            spiceline = 'port=%d' % spice['port']
            if 'disable-ticketing' in spice and spice['disable-ticketing']:
                spiceline += ',disable-ticketing'
            cmdline += [ '-spice', spiceline ]
            cmdline += [ '-vga', 'qxl' ]

        # vnc display
        if 'vnc' in vm['display']:
            vnc = vm['display']['vnc']
            assert 5900 <= vnc['port'] <= 65535
            cmdline += [ '-vnc', ':%d' % (vnc['port'] - 5900) ]

        # standard stuff
        cmdline += [ "-usbdevice", "tablet" ]
        cmdline += [ "-soundhw", "hda" ]

        cmdline += [ '-qmp', "tcp:127.0.0.1:%d,server,nowait" % vm['qmp-port'] ]
        cmdline += [ '-daemonize' ]
        cmdline += [ '-pidfile',  self._vm_pidfile(vm['name']) ]

        return cmdline

    def _temp_script(self):
        (fd, filename) = tempfile.mkstemp(text=True)
        fh = os.fdopen(fd, 'w')
        os.chmod(filename, stat.S_IXUSR | os.stat(filename).st_mode)
        return (fh, filename)
