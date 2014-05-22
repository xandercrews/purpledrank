__author__ = 'achmed'

'''
example documents for merging and relating(?) json documents


key_prefix: zpool_props
{
    "sourceid": x,
    "id": y
}

key_prefix: zpool_status
{
    "sourceid": x,
    "id": y
}


example docs:
{
  "sourceid": "twaughthammer",
  "timestamp": "2014-05-03T21:48:30.335035+00:00",
  "type": "zpool_properties",
  "id": "rpool",
  "_": {
    "comment": "-",
    "freeing": "0",
    "listsnapshots": "off",
    "delegation": "on",
    "dedupditto": "0",
    "dedupratio": "1.00x",
    "autoexpand": "off",
    "allocated": "14.4G",
    "guid": "18398111267391878995",
    "size": "37G",
    "capacity": "38%",
    "feature@multi_vdev_crash_dump": "disabled",
    "cachefile": "-",
    "bootfs": "rpool/ROOT/netatalk-3.0.1-1",
    "autoreplace": "off",
    "readonly": "off",
    "version": "-",
    "health": "ONLINE",
    "expandsize": "0",
    "feature@lz4_compress": "disabled",
    "feature@async_destroy": "enabled",
    "feature@empty_bpobj": "active",
    "free": "22.6G",
    "failmode": "wait",
    "altroot": "-"
  }
}

{
  "sourceid": "twaughthammer",
  "timestamp": "2014-05-03T21:49:20.817489+00:00",
  "type": "zpool_status",
  "id": "rpool",
  "_": {
    "status": "Some supported features are not enabled on the pool. The pool can still be used, but some features are unavailable.",
    "errors": "No known data errors",
    "name": "rpool",
    "spares": {},
    "scan": "scrub repaired 0 in 0h7m with 0 errors on Mon Jan  7 11:23:57 2013",
    "cache": {},
    "see": null,
    "vdevs": [
      {
        "state": "ONLINE",
        "disks": [
          {
            "state": "ONLINE",
            "name": "c3t0d0s0"
          },
          {
            "state": "ONLINE",
            "name": "c4t1d0s0"
          }
        ],
        "name": "mirror-0"
      }
    ],
    "state": "ONLINE",
    "action": "Enable all features using 'zpool upgrade'. Once this is done, the pool may no longer be accessible by software that does not support the features. See zpool-features(5) for details.",
    "logs": {}
  }
}

'''