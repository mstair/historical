Doing a release
===============

Doing a release of ``historical`` requires a few steps.

Bumping the version number
--------------------------

The next step in doing a release is bumping the version number in the
software.

* Update the version number in ``historical/__about__.py``.
* Set the release date in the :doc:`/changelog`.
* Do a commit indicating this.
* Send a pull request with this.
* Wait for it to be merged.

Performing the release
----------------------

The commit that merged the version number bump is now the official release
commit for this release. You will need to have ``gpg`` installed and a ``gpg``
key in order to do a release. Once this has happened:

* Run ``invoke release {version}``.

The release should now be available on PyPI and a tag should be available in
the repository.

Verifying the release
---------------------

You should verify that ``pip install historical`` works correctly:

.. code-block:: pycon

    >>> import historical
    >>> historical.__version__
    '...'

Verify that this is the version you just released.

Post-release tasks
------------------

* Update the version number to the next major (e.g. ``0.5.dev1``) in
  ``historical/__about__.py`` and
* Add new :doc:`/changelog` entry with next version and note that it is under
  active development
* Send a pull request with these items
* Check for any outstanding code undergoing a deprecation cycle by looking in
  ``historical.utils`` for ``DeprecatedIn**`` definitions. If any exist open
  a ticket to increment them for the next release.