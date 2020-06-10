from setuptools import setup
from os import path
import sys

# Load github README.md for the long description
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='cmdbench',
    url='https://github.com/manzik/cmdbench',
    author='Mohsen Yousefian',
    author_email='contact@manzik.com',
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
        'colorama',
        "matplotlib>=3.2.1"
    ],
    python_requires='>=3.5',
    version='0.1.7',
    download_url='https://pypi.org/project/cmdbench/',
    license='MIT',
    description='Quick and easy benchmarking for any command\'s CPU, memory, disk usage and runtime.',
    long_description=long_description,
    long_description_content_type='text/markdown',
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
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)

if __name__ == '__main__':
    if sys.platform == "darwin":
        raise Exception('Sorry, macOS is not supported.\nIf you would like to use cmdbench on macOS, please create an issue at https://github.com/manzik/cmdbench/issues to request the feature.')
