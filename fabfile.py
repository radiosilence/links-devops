# coding: utf-8
from __future__ import with_statement
import os
import random
import string

from contextlib import contextmanager as _contextmanager
from fabric.api import *
# from fabric.contrib.console import confirm

env.user = 'wsgi'
env.hosts = ['linkscreative.co.uk:22734']

env.repo = os.environ.get('REPO', None) or 'devops'
env.project = os.environ.get('PROJECT', None) or 'links-creative'
env.app = os.environ.get('APP', None) or env.repo
env.db_adapter = 'mysql'
env.db_user = os.environ.get('DB_USER')
env.db_password = os.environ.get('DB_PASSWORD')



def _random(length=16):
    return ''.join([random.choice(string.digits + string.letters + u'!-_:;.,^&')
                    for i
                    in range(0, length)])

@_contextmanager
def virtualenv():
    with cd(env.directory):
        with prefix(env.activate):
            yield

def _init(instance):
    env.instance = instance
    env.directory = u'/srv/{env.repo}/{env.instance}'.format(env=env)
    env.virtualenv = u'/env/{env.repo}/{env.instance}'.format(env=env)
    env.activate = u'source {env.virtualenv}/bin/activate'.format(env=env)

def generate_post_activate():
    variables = {
        'DJANGO_SETTINGS_MODULE': u'{env.app}.settings.production}'.format(env=env),
        'DJANGO_DB_PASSWORD': env.secrets['db'],
        'DJANGO_SETTINGS_MODULE': env.secrets['key'],
    }
    if env.instance == 'test':
        variables['DJANGO_SETTINGS_MODULE'] = u'{env.app}.settings.local'.format(env=env)



def pull():
    local("git pull --rebase")


def push():
    local("git push")


def install_requirements():
    run('pip install -r requirements.txt')


def setup_database_mysql():
    user = "'{env.repo}_{env.instance}'@'localhost'".format(env=env)
    db = '{env.repo}_{env.instance}'.format(env=env)
    run('echo "{commands}" | mysql -u {env.db_user} -p{env.db_password} '.format(env=env,
        commands=''.join([
            'CREATE DATABASE IF NOT EXISTS {db};'.format(db=db),
            "CREATE USER {user} IDENTIFIED BY '{password}';".format(
                user=user, password=env.secrets['db']),
            'GRANT ALL on {db}.* TO {user};'.format(db=db, user=user),
        ])
    ))

def setup_database():
    if env.db_adapter == 'postgres':
        setup_database_postgres()
    elif env.db_adapter == 'mysql':
        setup_database_mysql()

def create_instance(instance):
    _init(instance)
    env.secrets = {
        'db': _random(),
        'key': _random(64),
    }
    setup_database()
    run(u'mkdir -p {env.virtualenv}'.format(env=env))
    run(u'virtualenv {env.virtualenv}'.format(env=env))
    run(u'mkdir -p {}'.format(env.directory))
    with cd(env.directory):
        run(u'git clone git@codebasehq.com:linkscreative/{env.project}/{env.repo}.git .'.format(
            env=env
        ))

    with virtualenv():
        run('pip install -r requirements.txt')
    
    with virtualenv():
        run('python manage.py syncdb --noinput')
        run('python manage.py migrate --noinput')
        run('python manage.py collectstatic --noinput')

    print 'Database password:  {}'.format(env.secrets['db'])
    print 'Secret key:         {}'.format(env.secrets['key'])
    

def upgrade(instance):
    _init(instance)
    print(u'Updating {instance}'.format(instance=instance)) 

    pull()
    push()

    remote_path = _remote_path(instance)
    with cd(remote_path):
        run('git pull --rebase')
        install_requirements()
