"""Going online: who OAK box says it is, and checking certificates as the computer does.

Python checks HTTPS certificates with its own copy of the trust store; on Windows that copy can hold an old
cross-signed certificate leading to a root that expired in 2024, so a site the browser opens fine fails with
"certificate has expired". A county's network may also inspect HTTPS with its own root, which only the computer
knows. truststore makes every download (urllib, requests, OpenAVMKit's) check certificates the way the computer
does: Windows' own verifier, the Keychain on macOS, the system store on Linux.
"""

from __future__ import annotations

from oakbox import __version__

HOME = "https://github.com/larsiusprime/oakbox"
# Public services (OpenStreetMap's Overpass above all) ask apps to say who they are.
USER_AGENT = f"OAK box/{__version__} (+{HOME})"


def use_system_certificates() -> None:
    """Called first thing in every process OAK box starts (the app, Bring in data, model groups)."""
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001 - without it, Python's own certificate store is used, as before
        pass
