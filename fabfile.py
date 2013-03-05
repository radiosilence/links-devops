from __future__ import with_statement
from fabric.api import (
    abort,
    cd,
    local,
    run,
    settings,
)
from fabric.contrib.console import confirm

def pull():
    local("git pull --rebase")

def push():
    local("git push")

def upgrade(instance):
    print(u'Updating {instance}'.format(instance=instance)) 

    pull()
    push()
