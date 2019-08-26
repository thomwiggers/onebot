.. :changelog:

=======
History
=======

1.3.3 (2019-08-26)
------------------

* ``irc3``'s ``async`` plugin got renamed to ``asynchronious``.
    This means we now require `irc3>=1.1.3`
* In the URL plugin: read the response in 100KiB chunks and timeout

1.3.2 (2018-08-23)
------------------

* Actually release the below fix

1.3.1 (2018-08-23)
------------------

* Add ``Compatible: curl`` to ``User-Agent`` for ``urlinfo.py`` (contributed by `@mrngm`_ `PR #39`)

.. _PR #39: https://github.com/thomwiggers/onebot/pull/39

1.3.0 (2018-08-13)
------------------

* Support Python 3.7 (Requires `irc3>=1.1`)

1.2.1 (2018-03-05)
------------------

* Change urlinfo character limit to 320, helps twitter urls (contributed by `@mrngm`_ `PR #38`_)

.. _@mrngm: https://github.com/mrngm/
.. _PR #38: https://github.com/thomwiggers/onebot/pull/38

1.2.0 (2017-10-31)
------------------

* Truncate too long ``<title>`` tags in urlinfo output.
* Drop Python 3.3, 3.4 support

1.1.0 (2017-04-01)
------------------

* PSA Plugin (contributed by `@joostrijneveld`: `PR #32`_)
* Various contributions by `@Mattbox`_: `PR #36`_
  * Use musicbrainz tags instead of last.fm
  * Tests for PSA plugin
  * reload command
* Remove ``compare`` command as it's dead on Last.fm
* Remove ``mbid`` lookups on Last.fm as they're broken

.. _@joostrijneveld: https://github.com/joostrijneveld/
.. _@Mattbox: https://github.com/mattbox/
.. _PR #32: https://github.com/thomwiggers/onebot/pull/36
.. _PR #36: https://github.com/thomwiggers/onebot/pull/36

1.0.0 (2016-07-17)
------------------

I get around to finally posting this shit.

0.1.0 (2015-??)
------------------
First production usage

0.0.0 (2014-05-21)
------------------

Start of development
