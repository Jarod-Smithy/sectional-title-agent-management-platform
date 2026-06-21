"""Pure domain logic, ported from the prototype and decoupled from I/O.

These modules depend only on the ``ports`` Protocols and ``schemas`` — never on
sqlite, boto3, or FastAPI — so they are trivially unit-testable and run
unchanged on Lambda.
"""
