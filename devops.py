# coding: utf-8
from __future__ import with_statement
import os
import sys
import random
import string
import pipes
from tempfile import NamedTemporaryFile

from servers.servers import generate_config

from contextlib import contextmanager
from fabric.api import *
from fabric.contrib.console import confirm
from fabric.contrib.files import exists
from fabric.context_managers import warn_only
from fabric.colors import green, red
from fabric.contrib import django
from fabric.decorators import with_settings


env.user = 'wsgi'
env.hosts = ['linkscreative.co.uk:22734']
env.db_adapter = 'mysql'
env.db_user = os.environ.get('DB_USER') or 'root'
env.db_password = os.environ.get('DB_PASSWORD')
env.db_host = os.environ.get('DB_HOST') or 'localhost'

CWD = sys.path[0]


def debug():
    local('python manage.py runserver {host}:{port}'.format(
        host=os.environ.get('DJANGO_DEBUG_HOST', '0.0.0.0'),
        port=os.environ.get('DJANGO_DEBUG_PORT', env.debug_port)
    ))


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
    sys.path.insert(0, CWD)
    env.instance = instance
    if not env.repo:
        raise Exception('REPO not defined.')
    if not env.app:
        raise Exception('APP not defined.')
    if not env.instance:
        raise Exception('Instance not defined.')
    if not env.project:
        raise Exception('PROJECT not defined.')
    env.directory = u'/srv/{env.repo}/{env.instance}'.format(env=env)
    env.virtualenv = u'/env/{env.repo}/{env.instance}'.format(env=env)
    env.activate = u'source {env.virtualenv}/bin/activate'.format(env=env)
    env.source_vars = u'source {env.virtualenv}/bin/vars'.format(env=env)
    env.uwsgi_ini = u'{env.directory}/uwsgi.ini'.format(env=env)

    if env.instance == 'live':
        env.settings_variant = 'production'
    elif env.instance == 'test':
        env.settings_variant = 'development'
    else:
        env.settings_variant = instance
    if not hasattr(env, 'application'):
        puts(red('env.application defaulting to "static"'))
        env.application = 'static'

    if env.application == 'django':
        django.settings_module('{env.app}.settings.{env.settings_variant}'.format(
            env=env))


def generate_envvars():
    variables = {
        'DJANGO_SETTINGS_MODULE': u'{env.app}.settings.{env.settings_variant}'.format(env=env),
        'DJANGO_DB_PASSWORD': env.secrets['db'],
        'DJANGO_SECRET_KEY': env.secrets['key'],
    }
    env.envvars = variables
    


def install_requirements():
    with virtualenv():
        if exists('requirements.{env.instance}.txt'):
            run('pip install -r requirements.{env.instance}.txt'.format(
                env=env))
        elif exists('requirements.txt'):
            run('pip install -r requirements.txt'.format(
                env=env))
        else:
            puts(red('Requirements file not found.'))


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
    puts(green('Restarting uWSGI instance...'))
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
        for k, v in env.envvars.items():
            run('echo "export {0}={1}" >> bin/vars'.format(k, pipes.quote(v)))


def setup_database_mysql():
    user = "'{repo_short}_{env.instance}'@'localhost'".format(env=env,
        repo_short=env.repo[:11])
    db = '{env.repo}_{env.instance}'.format(env=env)

    run_mysql('CREATE DATABASE IF NOT EXISTS {db} CHARACTER SET utf8 COLLATE utf8_general_ci;'.format(db=db))
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
    if not confirm(red('Initialising a site will CHANGE THE DATABASE PASSWORD/SECRET KEY. Are you SURE you wish to continue?'), default=False):
        exit()

    env.secrets = {
        'db': _random(),
        'key': _random(64),
    }
    run(u'mkdir -p {env.virtualenv}/bin'.format(env=env))
    run(u'mkdir -p {}'.format(env.directory))
    generate_envvars()
    create_var_file()
    
    if not exists(env.activate):
        run(u'virtualenv {env.virtualenv}'.format(env=env))
        with virtualenv():
            run('pip install \'distribute>=0.6.35\'')
    with cd(env.directory):
        with settings(warn_only=True):
            result = run(u'git clone git@codebasehq.com:linkscreative/{env.project}/{env.repo}.git .'.format(
                env=env
            ))
            if result.failed:
                run('git pull --rebase')

    install_requirements()
    setup_database()
    

    if not hasattr(env, 'domains'):
        raise Exception('Need some domains!')

    nginx_config = {
        'type': 'nginx',
        'application': env.application,
    }
    if env.application == 'django':
        from django.conf import settings as djsettings
        nginx_config['media_url'] = djsettings.MEDIA_URL
        nginx_config['static_url'] = djsettings.STATIC_URL

    env.site = {
        'instances': [
            {
                'name': env.instance,
                'domains': env.domains,
            },
        ],
        'configs': [
            nginx_config,
        ],
    }
    conf_nginx()
    if env.application == 'django':
        with warn_only():
            manage('syncdb --noinput')
            manage('collectstatic --noinput')

        env.site['configs'].append({
            'type': 'uwsgi',
            'application': 'django',
            'app': env.app,
            'env': env.envvars
        })
        conf_uwsgi()
        

    for k, v in env.envvars.items():
        print(green('{0}: "{1}"'.format(k, v.replace('"', '\"'))))
    

def upgrade(instance):
    _init(instance)

    print(u'Updating {instance}'.format(instance=instance)) 

    local("git pull --rebase")
    local("git push")

    with virtualenv():
        run('git pull --rebase')
        install_requirements()

        if env.application == 'django':
            with warn_only():
                manage('syncdb --noinput')
                manage('migrate --noinput')
                manage('collectstatic --noinput')

        restart()

def shell(instance, *args, **kwargs):
    _init(instance)
    manage('shell_plus')


def conf_nginx():
    f = NamedTemporaryFile('w', delete=False)
    f.write(generate_config(
        env.repo,
        env.site,
        filter(lambda x: x['name'] == env.instance, env.site['instances'])[0],
        filter(lambda x: x['type'] == 'nginx', env.site['configs'])[0],
        '.conf',
    ))
    f.close()
    with virtualenv():
        put(f.name, 'nginx.conf')
    os.unlink(f.name)


def conf_uwsgi():
    f = NamedTemporaryFile('w', delete=False)
    f.write(generate_config(
        env.repo,
        env.site,
        filter(lambda x: x['name'] == env.instance, env.site['instances'])[0],
        filter(lambda x: x['type'] == 'uwsgi', env.site['configs'])[0],
        '.ini',
    ))
    f.close()
    with virtualenv():
        put(f.name, 'uwsgi.ini')
    os.unlink(f.name)


def celery(instance=None):
    instance = instance or 'local'
    _init(instance)
    if instance == 'local':
        loglevel = '--loglevel=INFO'
    else:
        loglevel = ''
    local('DJANGO_SETTINGS_MODULE={env.app}.settings.celery_{env.settings_variant} python manage.py celery worker -B {loglevel}'.format(env=env, loglevel=loglevel))
