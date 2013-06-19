# -*- coding: utf-8 -*-
from distutils.core import setup
from setuptools import find_packages


requires = []
dep_links = []

for dep in open('requirements.txt').read().split("\n"):
    if dep.startswith('git+') or dep.startswith('-e'):
        dep_links.append(dep)
    else:
        requires.append(dep)


setup(
    name="links-devops",
    version="0.1.7",
    description="Fabric deployment script.",
    author=u"James Cleveland",
    author_email="james@dapperdogstudios.com",
    url="https://linkscreative.codebasehq.com/projects/links-creative/repositories/devops",
    py_modules=['links_devops'],
    include_package_data=True,
    install_requires=requires,
    dependency_links=dep_links,
    classifiers=[
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Framework :: Django",
        ],
    zip_safe=False,
)
