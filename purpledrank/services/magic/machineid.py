__author__ = 'achmed'

import os
import socket
import random
import string

REPO_TOPDIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', '..'))
MACHINE_ID_PATH = '%s/machineid' % REPO_TOPDIR

import logging
logger = logging.getLogger(__name__)

def get_machine_id():
    '''
    get the machine ID, or persist a new one
    '''
    if not os.path.isfile(MACHINE_ID_PATH):
        new_id = "%s-%s" % (socket.gethostname(), ''.join(random.sample(string.ascii_lowercase + string.digits, 7)))
        ### not necessary to create parent dirs while the repo dir is in use
        # try:
        #     os.makedirs(os.path.dirname(MACHINE_ID_PATH))
        # except Exception, e:
        #     print e
        with open(MACHINE_ID_PATH, 'w') as fh:
            fh.write(new_id)
            logger.info('generated new machine id: %s' % new_id)
            return new_id
    else:
        with open(MACHINE_ID_PATH, 'r') as fh:
            machine_id = fh.read().strip()
            assert len(machine_id) < 256, 'machine id cannot exceed 255 characters'
            logger.info('machine id: %s' % machine_id)
            return machine_id
