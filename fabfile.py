from fabric.api import env
from devops import initialise, upgrade

env.repo = 'links-devops'
env.project = 'links-creative'
env.app = env.repo
env.domains = ['derp.linkscreative.co.uk']
