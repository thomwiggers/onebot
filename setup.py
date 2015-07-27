#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals, print_function

import sys

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


readme = open('README.rst').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

install_requires = ['irc3>=0.8.0', 'wheel', 'lfmh']
test_requires = ['pytest>=2.6', 'freezegun']

if sys.version_info < (3, 4):
    install_requires.append('trollius')
if sys.version_info < (3, 3):
    test_requires.append('mock')


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)


setup(
    name='onebot',
    version='0.1.0',
    description='OneBot is an ircbot based on irc3',
    long_description=readme + '\n\n' + history,
    author='Thom Wiggers',
    author_email='thom@thomwiggers.nl',
    url='https://github.com/thomwiggers/onebot',
    packages=find_packages(
        exclude=['*.tests', 'tests', 'tests.*', '*.tests.*']
    ),
    include_package_data=False,
    install_requires=install_requires,
    license='BSD',
    zip_safe=True,
    keywords='onebot irc',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    tests_require=test_requires,
    cmdclass={'test': PyTest},
    entry_points={
        'console_scripts': [
            'onebot = onebot:run',
        ]
    }
)
