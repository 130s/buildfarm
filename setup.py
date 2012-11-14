#!/usr/bin/env python

from setuptools import setup

# Prevent "TypeError: 'NoneType' object is not callable" error
# when running `python setup.py test`
# (see http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
try:
    import multiprocessing
except ImportError:
    pass

setup(name='buildfarm',
      version='0.0.1',
      packages=['buildfarm'],
      package_dir = {'buildfarm':'buildfarm'},
      scripts = ['scripts/setup_apt_root.py',
                 'scripts/list_all.py',
                 'scripts/repo_statuses_update',
                 'scripts/repo_statuses_publish',
                 'scripts/rosci',
                 'scripts/rosci-catkin-depends',
                 'scripts/rosci-clean-junit-xml'],
      package_data = {'buildfarm': ['resources/templates/*.em', 'resources/templates/*/*']},
      install_requires = ['PrettyTable', 'vcstools', 'rospkg'],
      test_requires = ['nose'],
      test_suite = 'nose.collector',
      author = "Tully Foote", 
      author_email = "tfoote@willowgarage.com",
      url = "http://www.ros.org/wiki/",
      download_url = "http://pr.willowgarage.com/downloads/buildfarm/", 
      keywords = ["ROS"],
      classifiers = [
        "Programming Language :: Python", 
        "License :: OSI Approved :: BSD License" ],
      description = "ROS package library", 
      long_description = """\
A library for interacting with the Catkin buildfarm.
""",
      license = "BSD"
      )
