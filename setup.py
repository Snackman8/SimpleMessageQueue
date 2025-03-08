#!/usr/bin/env python

from distutils.core import setup

setup(name='SimpleMessageQueue',
      version='1.0',
      description='Simple Message Queue',
      author='Lawrence Yu',
      author_email='lawy888@gmail.com',
      url='https://github.com/Snackman8/SimpleMessageQueue',
      packages=['SimpleMessageQueue'],
      include_package_data=False,
      entry_points={
        'console_scripts': ['SMQ_Server=SimpleMessageQueue.SMQ_Server:console_entry'],
      }
)
