from fabric.api import run, cd, env, settings, prefix
from fabric.context_managers import shell_env
import os
import yaml

REPO_TOPDIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

REPO_URL="git@github.com:xandercrews/purpledrank.git"

PID_FILE = "conf/supervisord.pid"
SUPERVISOR_CONF = 'conf/supervisor.conf'

env.use_ssh_config = True
env.forward_agent = True

def get_config():
    with open(os.path.join(REPO_TOPDIR, 'conf/config.yaml')) as fh:
        return yaml.load(fh)

def deploy(gittag=None):
    new_git_dir = False
    code_dir = 'purpledrank/'
    venv_dir = 'venv/purpledrank/'

    # clone code
    with settings(warn_only=True):
        if run('test -d %s' % code_dir).failed:
            new_git_dir = True
    if new_git_dir:
        run('mkdir -p %s' % code_dir)
        run('git clone %s %s' % (REPO_URL, code_dir,))

    # checkout newest version
    with cd(code_dir):
        run('git pull')
        if gittag:
            run('git checkout tags/%s' % gittag)
        else:
            run('git checkout master')

    # create virtualenv
    new_venv = False
    with settings(warn_only=True):
        if run('test -d %s' % venv_dir).failed:
            new_venv = True
    if new_venv:
        run('virtualenv %s -p `which python2.7`' % venv_dir)

    supervisor_running = True
    with cd(code_dir):
        with settings(warn_only=True):
            if run('[ -f %s ]' % PID_FILE).failed:
                supervisor_running = False
            if run('read PID < %s; [ -d /proc/${PID} ]' % PID_FILE).failed:
                supervisor_running = False

    if not supervisor_running:
        # run supervisor
        with prefix('. %s/bin/activate' % venv_dir.strip('/')):
            with shell_env(PYTHONPATH=code_dir):
                assert 'Python 2.7' in run('python --version'), 'require python 2.7'
                run('supervisord -c %s' % SUPERVISOR_CONF)

    # config = get_config()
    # assert 'common' in config, 'config must have common section'
    # assert 'magicport' in config['common'], 'config must have magic port in common section'
    # magic_port = config['common']['magicport']

    # activate venv
    # with prefix('. %s/bin/activate' % venv_dir.strip('/')):
    #     with shell_env(PYTHONPATH=code_dir):
    #         assert 'Python 2.7' in run('python --version'), 'require python 2.7'
    #         TODO install deps with setup.py
    #         run supervisor
    #         run('PYTHONPATH=%s zerorpc --bind tcp://0.0.0.0:%d purpledrank.services.magic.MagicService' % (magic_port))
