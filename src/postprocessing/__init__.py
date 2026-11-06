"""Shared code for the Paperless-ngx post-processing scripts.

Modules:

- ``config``: settings from the environment and ``.env``, and logging set-up
- ``paperless``: a small client for the Paperless-ngx REST API
- ``ai``: the OpenAI wrapper that returns parsed JSON replies
- ``correspondent``: choosing and assigning a document's correspondent
- ``metadata``: generating a title and filling custom fields
- ``pipeline``: running those steps on one document
- ``cli``: shared start-up code for the scripts in ``src/``
"""
