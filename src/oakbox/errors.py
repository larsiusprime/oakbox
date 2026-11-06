"""Why a request can't be answered, said so its route can give the right status.

- `NotFound` (404): what it names isn't there: a step, a field, a file, a model group, a sale.
- `NotReady` (409): an earlier step hasn't left what this starts from yet ("Bring in data first: …").

Both are LookupErrors. A route catches these, never LookupError itself, so a KeyError from a bug is a 500 with its
traceback in the log, not "No such step or field". The app answers either one that no route caught with its status
(app.create_app).
"""


class NotFound(LookupError):
    """What the request names isn't there."""


class NotReady(LookupError):
    """An earlier step has to run first; the message says which, in words the screen shows."""
