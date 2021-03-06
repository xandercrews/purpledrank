_all__ = ["monotonic_time"]

'''
stackoverflow-ware
http://stackoverflow.com/questions/1205722/how-do-i-get-monotonic-time-durations-in-python
'''

import ctypes, os, sys

# linux
CLOCK_MONOTONIC_RAW = 4 # see <linux/time.h>
CLOCK_MONOTONIC = 1 # see <linux/time.h>

# solaris
CLOCK_HIGHRES = 4

class timespec(ctypes.Structure):
    _fields_ = [
        ('tv_sec', ctypes.c_long),
        ('tv_nsec', ctypes.c_long)
    ]

librt = ctypes.CDLL('librt.so.1', use_errno=True)
clock_gettime = librt.clock_gettime
clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(timespec)]

def monotonic_time(raw=False):
    if sys.platform.startswith('sunos'):
        TIMER = CLOCK_HIGHRES
    else:
        if raw:
            TIMER = CLOCK_MONOTONIC_RAW
        else:
            TIMER = CLOCK_MONOTONIC

    t = timespec()
    if clock_gettime(TIMER, ctypes.pointer(t)) != 0:
        errno_ = ctypes.get_errno()
        raise OSError(errno_, os.strerror(errno_))
    return t.tv_sec + t.tv_nsec * 1e-9

if __name__ == "__main__":
    print monotonic_time()
