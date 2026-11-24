"""Entry point for the packaged executable.

``python -m markvist`` runs ``markvist/__main__.py`` as part of the package,
but a frozen build runs its entry script as ``__main__`` with no package
context, so the relative import there cannot work. This script imports the
package absolutely; ``--paths src`` lets PyInstaller find it at build time.
"""

from markvist.app import main

if __name__ == "__main__":
    raise SystemExit(main())
