__author__ = 'achmed'

import subprocess

def _generic_command(cmd, *args):
    '''
    suitable for commands which require no input and for which you only care about
    output on stdout, and which cannot stall or receive incomplete results from p.communicate()
    '''
    p = subprocess.Popen([cmd] + list(args), stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    rc = p.returncode

    if rc != 0:
        raise Exception('%s failed: %s' % (cmd, stderr,))

    return stdout
