from setuptools import setup

setup(
    # Needed to silence warnings (and to be a worthwhile package)
    name='cmdbench',
    url='https://github.com/manzik/cmdbench',
    author='Mohsen Yousefian',
    author_email='me@manzik.com',
    # Needed to actually package something
    packages=['cmdbench'],
    keywords = ['benchmarks', 'benchmark', 'benchmarking', 'profiler', 'profiling', 
                'timeit', 'time', 'runtime', 'performance', 'monitoring', 'monitor',
                'cpu', 'memory', 'ram', 'disk'],
    # Needed for dependencies
    install_requires=[
        'numpy', 
        'psutil>=5.7.0', 
        'beeprint>=2.4.10', 
        'Click',
        'tqdm',
        'colorama'
    ],
    extras_require = {
        "resources_plotting":  ["matplotlib>=3.2.1"]
    },
    # *strongly* suggested for sharing
    version='0.1',
    # The license can be anything you like
    license='MIT',
    description='Quick and easy benchmarking for any command\'s CPU, memory, disk usage and runtime.',
    entry_points={
        "console_scripts": [
            "cmdbench = cmdbench.cli:benchmark"
            ]
        },
    classifiers=[
        'Development Status :: 3 - Alpha',      # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'Topic :: Software Development :: Testing',
        'Topic :: System :: Benchmark',
        'Topic :: Utilities',
        'Operating System :: Unix',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',      #Specify which pyhton versions that you want to support
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    # We will also need a readme eventually (there will be a warning)
    # long_description=open('README.txt').read(),
)

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        raise Exception('Sorry, Python 2 is not supported.')
        
    if sys.platform == "darwin":
        raise Exception('Sorry, macOS is not supported.\nIf you would like to use cmdbench on macOS, please create an issue at https://github.com/manzik/cmdbench/issues to request the feature.')
