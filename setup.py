
from os.path import abspath, dirname, join
from setuptools import find_packages, setup
from speakreader import PRODUCT, VERSION_RELEASE

def read_file(filename):
    """Read the contents of a file located relative to setup.py"""
    with open(join(abspath(dirname(__file__)), filename)) as thefile:
        return thefile.read()

setup(
    name=PRODUCT,
    version=VERSION_RELEASE,
    author="Jerry Nance",
    author_email="jerry@nance.us",
    description="Serve Speech-to-Text to many concurrently in realtime.",
    long_description=read_file("README.MD"),
    long_description_content_type="text/markdown",
    url="",
    packages=find_packages(),
    package_data={},
    python_requires='>=3.6.*',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License V3 (GPLV3)",
        "Operating System :: OS Independent",
        "Framework :: CherryPY",
    ],
    install_requires=[
        'CherryPy',
        'portend',
        'Mako',
        'configobj',
        'PyAudio',
        'pywin32; sys_platform == "win32"',
        'pyjwt',
        'httplib2',
        'python-dateutil',
        'tzlocal',
        'passlib',
        'wheel',
        'samplerate',
        'google-cloud-speech',
        'google-api-python-client',
        'ibm-watson',
        'azure-cognitiveservices-speech; (sys_platform in "win32 macos") or (sys_platform == "linux" and platform_machine in "AMD64")',
    ],
)
