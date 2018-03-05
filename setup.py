#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals, print_function

import sys

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


readme = open('README.rst').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

install_requires = [
    'irc3>=0.9',
    'wheel',
    'lfmh',
    'musicbrainzngs',
    'beautifulsoup4',
    'html5lib!=0.99999999',
    'requests']

test_requires = ['freezegun']
if sys.version_info > (3, 5):
    test_requires.append('pytest>=2.7.3')
else:
    test_requires.append('pytest>=2.6')


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
    version='1.2.1',
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
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    tests_require=test_requires,
    cmdclass={'test': PyTest},
    entry_points={
        'console_scripts': [
            'onebot = onebot:run',
        ]
    }
)
