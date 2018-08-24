'''A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
'''

from setuptools import setup
from setuptools import find_packages
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
try:
    with open(path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
except:
    long_description = ''

setup(name='pyzwaver',
      version='0.1.0',
      description='Z-Wave library written in Python3',
      long_description=long_description,
      url='https://github.com/robertmuth/PyZwaver',
      author='Robert Muth',
      author_email='robert@muth.org',
      license='License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      classifiers=[  # https://pypi.python.org/pypi?%3Aaction=list_classifiers
                   'Development Status :: 3 - Alpha',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Intended Audience :: Science/Research',
                   'Intended Audience :: Telecommunications Industry',
                   'Topic :: Software Development :: Build Tools',
                   'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                   'Natural Language :: English',
                   'Operating System :: POSIX :: Linux',
                   'Operating System :: Microsoft :: Windows',
                   'Operating System :: MacOS :: MacOS X',
                   'Programming Language :: Python :: 3',
                   'Topic :: Communications',
                   'Topic :: Communications :: Ham Radio',
                   'Topic :: Home Automation',
                   'Topic :: Security :: Cryptography'],
      keywords='zwave z-wave s2 s0 smarthome home home automation scene aeotec z-stick',
      packages=find_packages(),
      package_data={'pyzwaver': ['pyzwaver.iml']},  # support files
      install_requires=[],  # dependencies
      zip_safe=False)

# TODO: Include files (XML?  tests?)
