========
Usage
========

Use the ``onebot`` command to run stuff.

--------------
Configuration
--------------

You can use this sample configuration file:

.. literalinclude:: config.ini

Most options should mostly speak for themselves.
Note that the plugin settings are (obviously) plugin-dependant.
You should consult the manual for each plugin to figure out what you need to set.

This project is based on *irc3*.
irc3 plugins are compatible with OneBot.
Some OneBot plugins make use of irc3 modules.
See the module :mod:`onebot.plugin`.
You should consult the `irc3 documentation`__ for information about irc3 plugins.

__ irc3_

.. autofunction:: onebot.run

.. _irc3: http://irc3.readthedocs.io/
