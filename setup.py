from setuptools import setup

setup(
    # Needed to silence warnings (and to be a worthwhile package)
    name='cmdbench',
    url='https://github.com/manzik/cmdbench',
    author='Mohsen Yousefian',
    author_email='me@manzik.com',
    # Needed to actually package something
    packages=['cmdbench'],
    # Needed for dependencies
    install_requires=[
        'numpy', 
        'psutil>=5.7.0', 
        'beeprint>=2.4.10', 
        'Click',
    ],
    extras_require = {
        "resources_plotting":  ["matplotlib>=3.2.1"]
    },
    # *strongly* suggested for sharing
    version='0.1',
    # The license can be anything you like
    license='MIT',
    description='Quick and easy benchmarking for any command\'s CPU, memory and disk usage.',
    entry_points={
        "console_scripts": [
            "cmdbench = cmdbench.cli:benchmark"
            ]
        },
    # We will also need a readme eventually (there will be a warning)
    # long_description=open('README.txt').read(),
)

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        raise Exception('Sorry, Python 2 is not supported.')