# coding: utf-8
from devops import *
env.hosts = ['linkscreative.co.uk:22734']
env.db_adapter = 'mysql'
if not getattr(env, 'ignore_virtualenv_override', False):
    env.virtualenv_template = u'/env/{env.repo}/{env.instance}'
