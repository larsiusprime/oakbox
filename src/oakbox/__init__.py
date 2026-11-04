"""Oakbox: OpenAVMKit in a box."""

from importlib.metadata import PackageNotFoundError, version

# One version, pyproject.toml's: a release is tagged v<it> (.github/workflows/bundles.yml checks).
try:
    __version__ = version("oakbox")
except PackageNotFoundError:  # running from a checkout that isn't installed
    __version__ = "0.0.0+unknown"
