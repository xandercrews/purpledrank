__author__ = 'achmed'

import os
import yaml
import logging.config

REPO_TOPDIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..'))

def init_logger():
    with open(os.path.join(REPO_TOPDIR, 'conf', 'logging.yaml'), 'r') as fh:
        d = yaml.load(fh)

    logging.config.dictConfig(d)
