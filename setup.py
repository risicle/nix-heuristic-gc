# Available at setup time due to pyproject.toml
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

__version__ = "0.1.0"

ext_modules = [
    Pybind11Extension(
        "libstore_wrapper",
        ["src/main.cpp"],
        libraries = [ "nixstore" ],
        # Example: passing in the version to the compiled code
        define_macros = [('VERSION_INFO', __version__)],
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
    ext_modules=ext_modules,
    extras_require={},
    # Currently, build_ext only provides an optional "highest supported C++
    # level" feature, but in the future it may provide more features.
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.8",
)
