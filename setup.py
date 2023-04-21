# Available at setup time due to pyproject.toml
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

from os import environ

try:
    NIX_SYSTEM = environ["NIX_SYSTEM"]
except KeyError:
    raise EnvironmentError(
        "Please set NIX_SYSTEM environment variable"
        # or someone tell me how i can extract this automatically
    )

with open("VERSION", "r") as r:
    __version__ = r.read().strip()

ext_modules = [
    Pybind11Extension(
        "nix_heuristic_gc.libnixstore_wrapper",
        ["src/main.cpp"],
        libraries = [ "nixstore" ],
        # Example: passing in the version to the compiled code
        define_macros = [
            ('VERSION_INFO', __version__),
            ('NIX_SYSTEM', NIX_SYSTEM),
        ],
    ),
]

setup(
    name="nix-heuristic-gc",
    version=__version__,
    author="Robert Scott",
    author_email="code@humanleg.org.uk",
    url="https://github.com/risicle/nix-heuristic-gc",
    description="",
    long_description="",
    packages=["nix_heuristic_gc"],
    ext_modules=ext_modules,
    extras_require={},
    cmdclass={"build_ext": build_ext},
    entry_points={
        "console_scripts": ["nix-heuristic-gc=nix_heuristic_gc.__main__:main"],
    },
    zip_safe=False,
    python_requires=">=3.8",
    license="LGPL-2.1-or-later",
    classifiers=[
        "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)",
    ],
)
