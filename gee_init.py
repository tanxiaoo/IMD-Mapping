"""Earth Engine initialisation, with the Cloud project read from ``.env``.

Every notebook that touches Earth Engine needs a Cloud project id, and that id
differs per person: it is tied to whoever authenticated, not to the analysis.
Hardcoding it in each notebook means a pull is followed by editing every
notebook back, and the edits then show up as diffs on files nobody changed.

So the id lives in ``.env``, which is gitignored. Copy ``.env.example`` to
``.env`` once, put your own project id in it, and it never needs touching
again. Notebooks call:

    from gee_init import init_gee
    init_gee()

Resolution order, first hit wins:

  1. the ``project`` argument, if one is passed
  2. ``GEE_PROJECT`` in the process environment -- this is what lets CI or a
     shell override the file without editing it
  3. ``GEE_PROJECT`` in ``.env`` beside this file

No default is baked in. A missing id raises rather than silently falling back
to somebody else's project, which would fail later with an opaque permissions
error from Earth Engine instead of here with a sentence saying what to do.
"""

from pathlib import Path

import ee

ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env(path=ENV_PATH):
    """Parse a ``.env`` file into a dict.

    Deliberately minimal: ``KEY=value`` per line, ``#`` comments, optional
    surrounding quotes. No interpolation, no export statements. A missing file
    is not an error -- the environment variable path may be in use instead.
    """
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def get_project(project=None):
    """Return the Earth Engine Cloud project id, or raise saying how to set it."""
    import os

    resolved = project or os.environ.get("GEE_PROJECT") or load_env().get("GEE_PROJECT")
    if not resolved:
        raise RuntimeError(
            "No Earth Engine project id found. Copy .env.example to .env and set\n"
            "    GEE_PROJECT=your-cloud-project-id\n"
            f"Expected the file at {ENV_PATH}.\n"
            "Your project ids are listed at https://console.cloud.google.com/project"
        )
    return resolved


def init_gee(project=None, quiet=False):
    """Initialise Earth Engine against the configured Cloud project.

    Authentication is separate and is a one-off per machine: run
    ``earthengine authenticate`` in a shell, or ``ee.Authenticate()`` once in a
    notebook. This function does not call it -- ``ee.Authenticate()`` opens a
    browser flow, which would make every notebook run interactive.
    """
    resolved = get_project(project)
    ee.Initialize(project=resolved)
    if not quiet:
        print(f"GEE initialised (project: {resolved}).")
    return resolved
