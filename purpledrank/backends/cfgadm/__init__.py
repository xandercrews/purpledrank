__author__ = 'achmed'

from .. import backendutil
import re

import logging
logger = logging.getLogger(__name__)

CFGADM_CMD = '/usr/sbin/cfgadm'

# this works for me but the cfgadm output various alot
# need more patterns for different controller, bus types, etc
DISK_INFO_RE_PAT = re.compile('(Mod: (.*)) (FRev: (.*)) (SN: (.*))')
DISK_APID_RE_PAT = re.compile('(.*)::dsk/(.*)')

class CfgAdmDataInterface(object):
    @classmethod
    def cfgadm_disk_properties(cls):
        result = backendutil._generic_command(CFGADM_CMD, '-alv', '-s' 'noheadings,select=type(disk),cols=ap_id:r_state:o_state:condition:info,cols2=')

        return cls._parse_cfgadm_disks(result)

    @staticmethod
    def _parse_cfgadm_disks(output):
        lines = output.splitlines()

        disks = {}

        for line in lines:
            apid, rstate, ostate, condition, info = map(str.strip, line.split(None, 4))

            # parse info
            info = DISK_INFO_RE_PAT.match(info)

            if info is None:
                logger.error('info \'%s\' could not be parsed for line: %s' % (info, line.strip()))
                continue
            else:
                sn = info.group(6)
                frev = info.group(4)
                model = info.group(2)

            # parse apid
            apid = DISK_APID_RE_PAT.match(apid)

            if apid is None:
                logger.error('apid \'%s\' could not be parsed for line: %s' % (apid, line.strip()))
                continue
            else:
                controller = apid.group(1)
                disk = apid.group(2)

            diskprops = dict(name=disk, controller=controller, rstate=rstate, ostate=ostate, condition=condition, sn=sn, frev=frev, model=model)
            disks[disk] = diskprops

        return disks
