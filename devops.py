# coding: utf-8
from __future__ import with_statement
import os
import random
import string
import pipes

from contextlib import contextmanager
from fabric.api import *
from fabric.contrib.console import confirm
from fabric.colors import green
from fabric.decorators import with_settings


env.user = 'wsgi'
env.hosts = ['linkscreative.co.uk:22734']
env.db_adapter = 'mysql'
env.db_user = os.environ.get('DB_USER') or 'root'
env.db_password = os.environ.get('DB_PASSWORD')
env.db_host = os.environ.get('DB_HOST') or 'localhost'


def _random(length=16):
    return ''.join([random.choice(string.digits + string.letters + u'!-_:;.,^&')
                    for i
                    in range(0, length)])

@contextmanager
def virtualenv():
    with cd(env.directory):
        with prefix(env.activate):
            with prefix(env.source_vars):
                yield


def _init(instance):
    env.instance = instance
    if not env.app:
        raise Exception('APP not defined.')
    if not env.repo:
        raise Exception('REPO not defined.')
    if not env.instance:
        raise Exception('Instance not defined.')
    if not env.project:
        raise Exception('PROJECT not defined.')
    env.directory = u'/srv/{env.repo}/{env.instance}'.format(env=env)
    env.virtualenv = u'/env/{env.repo}/{env.instance}'.format(env=env)
    env.activate = u'source {env.virtualenv}/bin/activate'.format(env=env)
    env.source_vars = u'source {env.virtualenv}/bin/vars'.format(env=env)
    env.uwsgi_ini = u'{env.directory}/uwsgi.ini'.format(env=env)


def generate_vars():
    variables = {
        'DJANGO_SETTINGS_MODULE': u'{env.app}.settings.production'.format(env=env),
        'DJANGO_DB_PASSWORD': env.secrets['db'],
        'DJANGO_SECRET_KEY': env.secrets['key'],
    }
    if env.instance == 'test':
        variables['DJANGO_SETTINGS_MODULE'] = u'{env.app}.settings.development'.format(env=env)
    return variables
    


def install_requirements():
    run('pip install -r requirements.txt')

@with_settings(warn_only=True)
def run_mysql(command):
    if not env.db_user:
        raise Exception('Control DB user not set!')
    if not env.db_password:
        raise Exception('Control DB password not set!')
    if not env.db_host:
        raise Exception('Control DB host not set!')

    run('echo "{command}" | mysql -u {env.db_user} -p{env.db_password} '.format(env=env,
        command=command
    ))


def restart():
    with virtualenv():
        run('touch {env.uwsgi_ini}'.format(env=env))


def manage(command):
    with virtualenv():
        run('python manage.py {command}'.format(
            command=command
        ))


def create_var_file():
    with cd(env.virtualenv):
        run('echo > bin/vars')
        for k, v in generate_vars().items():
            run('echo "export {0}={1}" >> bin/vars'.format(k, pipes.quote(v)))


def setup_database_mysql():
    user = "'{env.repo}_{env.instance}'@'localhost'".format(env=env)
    db = '{env.repo}_{env.instance}'.format(env=env)
    
    run_mysql('CREATE DATABASE IF NOT EXISTS {db};'.format(db=db))
    run_mysql('DROP USER {user}'.format(user=user))
    run_mysql("CREATE USER {user} IDENTIFIED BY '{password}';".format(
        user=user, password=env.secrets['db']))
    run_mysql('GRANT ALL on {db}.* TO {user};'.format(db=db, user=user))


def setup_database():
    if env.db_adapter == 'postgres':
        setup_database_postgres()
    elif env.db_adapter == 'mysql':
        setup_database_mysql()


def initialise(instance):
    _init(instance)
    if not confirm("Initialising a site will CHANGE THE DATABASE PASSWORD/SECRET KEY. Are you SURE you wish to continue?", default=False):
        exit()

    env.secrets = {
        'db': _random(),
        'key': _random(64),
    }
    setup_database()
    create_var_file()
    run(u'mkdir -p {env.virtualenv}'.format(env=env))
    run(u'virtualenv {env.virtualenv}'.format(env=env))
    run(u'mkdir -p {}'.format(env.directory))
    with cd(env.directory):
        with settings(warn_only=True):
            result = run(u'git clone git@codebasehq.com:linkscreative/{env.project}/{env.repo}.git .'.format(
                env=env
            ))
            if result.failed:
                run('git pull --rebase')

    with virtualenv():
        run('pip install \'distribute>=0.6.35\'')
        run('pip install -r requirements.txt')

    for k, v in generate_vars().items():
        print(green('{0}: "{1}"'.format(k, v.replace('"', '\"'))))
    

def upgrade(instance):
    _init(instance)

    print(u'Updating {instance}'.format(instance=instance)) 

    local("git pull --rebase")
    local("git push")

    with virtualenv():
        run('git pull --rebase')
        run('pip install -r requirements.txt')