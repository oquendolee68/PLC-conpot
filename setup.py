from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages


def get_requirements():
    with open('requirements.txt') as req_file_h:
        reqs = []
        for line in req_file_h.read().splitlines():
            if not line.startswith("https"):
                reqs.append(line)
    return reqs


setup(
    name='Conpot',
    version='0.1.0',
    packages=find_packages(exclude=["*.pyc", "config.py"]),
    package_data = {
        '': ['*.txt', '*.rst'],
        'conpot': ['templates/*.xml', 'conpot.cfg', "tests/data/*"],
    },
    url='http://conpot.org',
    license='GPL 2',
    author='Glastopf Project',
    author_email='glastopf@public.honeynet.org',
    description="""Conpot is an ICS honeypot with the goal to collect intelligence about the motives
    and methods of adversaries targeting industrial control systems""",
    long_description=open('README.rst').read(),
    classifiers  = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Topic :: Security",
        ],
    keywords="ICS SCADA honeypot",
    scripts=['bin/conpot'],
    test_suite='nose.collector',
    tests_require="nose",
    install_requires=get_requirements(),
    dependency_links = [
        "git+git://github.com/rep/hpfeeds.git"
        "git+git://github.com/glastopf/modbus-tk.git"
    ],
)