# coding: utf-8
from devops import *
env.hosts = ['linkscreative.co.uk:22734']
env.db_adapter = 'mysql'
if not env.ignore_virtualenv_override:
    env.virtualenv_template = u'/env/{env.repo}/{env.instance}'
