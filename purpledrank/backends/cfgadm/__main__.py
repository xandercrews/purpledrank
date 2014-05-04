__author__ = 'achmed'

from . import CfgAdmDataInterface

if __name__ == "__main__":
    cfgoutput = """
sata0/0::dsk/c3t0d0            connected    configured   ok         Mod: SAMSUNG HD040GJ FRev: WY100-33 SN: S09UJ10Y523922
sata0/1::dsk/c3t1d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA3MA SN: JP9960HZ1JRXSU
sata0/2::dsk/c3t2d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA39C SN: JP2921HQ1T451A
sata0/3::dsk/c3t3d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA3MA SN: JP2940HZ1KGALC
sata0/4::dsk/c3t4d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA3MA SN: JP2940HZ1K47VC
sata0/5::dsk/c3t5d0            connected    configured   ok         Mod: WDC WD1001FALS-00J7B1 FRev: 05.00K05 SN: WD-WMATV4110916
sata0/6::dsk/c3t6d0            connected    configured   ok         Mod: WDC WD1001FALS-00J7B1 FRev: 05.00K05 SN: WD-WMATV3999684
sata1/0::dsk/c4t0d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA39C SN: JP2921HQ1V6DBA
sata1/1::dsk/c4t1d0            connected    configured   ok         Mod: SAMSUNG HD040GJ/P FRev: ZG100-34 SN: S0DDJ1LL708213
sata1/2::dsk/c4t2d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA39C SN: JP2921HQ1RRN4A
sata1/3::dsk/c4t3d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA3EA SN: JP2940HD0DLPAC
sata1/4::dsk/c4t4d0            connected    configured   ok         Mod: WDC WD1001FALS-00J7B1 FRev: 05.00K05 SN: WD-WMATV4126215
sata1/5::dsk/c4t5d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA3MA SN: JP2940HZ1K478C
sata1/6::dsk/c4t6d0            connected    configured   ok         Mod: Hitachi HDS721010CLA332 FRev: JP4OA3MA SN: JP9960HZ1JER4U
sata1/7::dsk/c4t7d0            connected    configured   ok         Mod: WDC WD1001FALS-00J7B1 FRev: 05.00K05 SN: WD-WMATV4258827
""".lstrip()

    import pprint
    pprint.pprint(CfgAdmDataInterface._parse_cfgadm_disks(cfgoutput), indent=2)
