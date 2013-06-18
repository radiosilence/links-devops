# coding: utf-8
from devops import *
env.user = 'wsgi'
env.hosts = ['linkscreative.co.uk:22734']
env.db_adapter = 'mysql'
env.virtualenv_template = u'/env/{env.repo}/{env.instance}'

