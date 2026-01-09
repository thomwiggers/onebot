============
Installation
============

To run OneBot you need at least Python 3.11.

At the command line::

    $ pip install onebot

Or, if you have virtualenvwrapper installed::

    $ mkvirtualenv onebot
    $ pip install onebot

You should now have the ``onebot`` command available.

Docker
------

You can also run OneBot using Docker and Docker Compose. This is especially
useful if you want to use the Python sandbox feature without giving the bot
access to your host's Docker socket.

A sample ``docker-compose.yml`` is provided in the ``docs/`` directory. To use it:

1. Copy ``docs/docker-compose.yml.example`` to your project root as ``docker-compose.yml``.
2. Create a ``config/`` directory and place your ``config.ini`` there.
3. Run ``docker compose up -d``.

.. literalinclude:: docker-compose.yml.example
    :language: yaml
    :caption: docs/docker-compose.yml.example
