__author__ = 'achmed'

import os
import socket
import random
import string

REPO_TOPDIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', '..'))
AGENT_ID_PATH = '%s/agentid' % REPO_TOPDIR

import logging
logger = logging.getLogger(__name__)

def get_agent_id():
    '''
    get the agent ID, or persist a new one
    '''
    if not os.path.isfile(AGENT_ID_PATH):
        new_id = "%s-%s" % (socket.gethostname(), ''.join(random.sample(string.ascii_lowercase + string.digits, 7)))
        ### not necessary to create parent dirs while the repo dir is in use
        # try:
        #     os.makedirs(os.path.dirname(AGENT_ID_PATH))
        # except Exception, e:
        #     print e
        with open(AGENT_ID_PATH, 'w') as fh:
            fh.write(new_id)
            logger.info('generated new agent id: %s' % new_id)
            return new_id
    else:
        with open(AGENT_ID_PATH, 'r') as fh:
            agent_id = fh.read().strip()
            assert len(agent_id) < 256, 'agent id cannot exceed 255 characters'
            logger.info('agent id: %s' % agent_id)
            return agent_id
