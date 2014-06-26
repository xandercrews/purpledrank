from ..baseservice import BaseService

from ...backends import kvm

from ...timeutil import utctimestamp
from ...envelopeutil import make_envelope

import functools

import gevent.pool

class KVMService(BaseService):
    def __init__(self):
        BaseService.__init__(self)
        self.ki = kvm.KVMInventoryInterface()
        self.kc = kvm.KVMCommandInterface(self.ki)
        self.sourceid = self.config['sourceid']

    def get_vm(self, vmname):
        """
        returns vm information by name
        """
        timestamp = utctimestamp()

        return self._get_vm(timestamp, vmname)

    def get_all_vms(self):
        """
        returns all vm information by name
        """
        # TODO prevent one bad VM from tainting all results
        timestamp = utctimestamp()

        vm_getter = functools.partial(self._get_vm, timestamp)

        pool = gevent.pool.Pool(20)

        return list(pool.imap_unordered(vm_getter, self.ki.list_vms()))

    def get_running_vms(self):
        """
        return a list of the vms currently running
        """
        return filter(self.kc._vm_is_running, self.ki.list_vms())

    def list_vms(self):
        """
        returns a list of vms in inventory
        """
        return self.ki.list_vms()

    def list_invalid_vmfiles(self):
        """
        returns a list of vm files present but invalid
        """
        return self.ki.list_invalid_vmfiles()

    def start_vm(self, vmname):
        """
        starts a vm by name
        """
        self.kc.start(vmname)
        return True

    def start_migrate_target(self, vmname, migrateport):
        """
        starts a vm in incoming/migrate mode
        """
        return self.kc.start_migrate_target(vmname, migrateport)

    def migrate(self, vmname, targethost, targetport, speedinkb=None, downtimeinseconds=None, spicehost=None, spiceticket=None):
        """
        starts a vm migration to a remote target
        """
        return self.kc.migrate(vmname, targethost, targetport, speedinkb, downtimeinseconds, spicehost, spiceticket)

    def shutdown_vm(self, vmname):
        """
        sends the vm a signal to shut down (may or may not work)
        """
        self.kc.shutdown(vmname)
        return True

    def kill_vm(self, vmname):
        """
        stops a vmm immediately
        """
        self.kc.kill(vmname)
        return True

    def generate_spice_ticket(self, vmname, expiry='+300'):
        """
        assigns and returns a temporary spice access ticket at random
        """
        ticket = self.kc._generate_spice_ticket()
        self.kc.set_spice_ticket(vmname, ticket, expiry)
        return ticket

    def monitor_command(self, vmname, command, *args):
        """
        issues an arbitrary monitor command to vm
        """
        return self.kc.mon_command(vmname, command, *args)

    def _get_vm(self, timestamp, vmname):
        # fetch vm information from backend services and combine results
        vmconfig, running, runtime = self.kc.vm_info(vmname)
        vminfo = dict(running=running, config=vmconfig, runtime=runtime)

        return make_envelope(vminfo, vmname, 'kvm_vm', self.sourceid, timestamp)

