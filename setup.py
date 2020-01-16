from setuptools import setup, find_packages

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='sobchak',
    version='0.2',
    description='OpenStack instance scheduling optimizer',
    license='MIT',
    long_description=long_description,
    author='Joris Hartog',
    author_email='jorishartog@hotmail.com',
    url='curlba.sh/jhartog/sobchak',
    long_description_content_type='text/markdown',
    packages=find_packages(),
    scripts=['scripts/sobchak'],
    install_requires=[
        'python-keystoneclient',
        'python-novaclient',
        'matplotlib',
    ],
)

