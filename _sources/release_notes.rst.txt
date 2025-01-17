=======================================================================================
eToolBox Release Notes
=======================================================================================

.. _release-v0-3-1:

---------------------------------------------------------------------------------------
0.3.1 (2024-XX-XX)
---------------------------------------------------------------------------------------

What's New?
^^^^^^^^^^^
*  Use :mod:`pyarrow` directly in :func:`.pd_read_pudl` to avoid having dates cast to
   objects.
*  Compatibility with Python 3.13 tested and included in CI.
*  Declaring optional cloud dependencies of :mod:`pandas` and :mod:`polars` explicitly.
*  Tools for working with data stored on Azure.
*  :class:`.DataZip` now recognizes alternative methods for getting and setting object
   state so that an object can specify a serialization for :class:`.DataZip` that is
   different than that for :mod:`pickle`. These new methods are ``_dzgetstate_``
   and ``_dzsetstate_``.
*  :func:`.storage_options` to simplify reading from/writing to Azure using
   :mod:`pandas` or :mod:`polars`.
*  :func:`.generator_ownership` compiles ownership information for all generators using
   data from :mod:`pudl`.
*  New CLI built off a single command ``rmi`` with ``cloud`` and ``pudl`` subcommands
   for cleaning caches and configs.

Bug Fixes
^^^^^^^^^
*  Fixed a bug in the implementation of the alternative serialization methods that
   caused recursion or other errors when serializing an object whose class implemented
   ``__getattr__``.
*  Attempt to fix doctest bug caused by pytest logging, see
   `pytest#5908 <https://github.com/pytest-dev/pytest/issues/5908>`_

.. _release-v0-3-0:

---------------------------------------------------------------------------------------
0.3.0 (2024-10-07)
---------------------------------------------------------------------------------------

What's New?
^^^^^^^^^^^
*  New functions to read :mod:`pudl` tables from parquets in an open-access AWS bucket
   using :func:`.pd_read_pudl`, :func:`.pl_read_pudl`, and :func:`.pl_scan_pudl` which
   handle caching. :mod:`polars` AWS client does not currently work so ``use_polars``
   must be set to ``False``.
*  New :func:`.pudl_list` to show a list of releases or tables within a release.
*  Restricting ``platformdirs`` version to >= 3.0 when config location changed.
*  **Removed**:

   *  :func:`read_pudl_table`
   *  :func:`get_pudl_tables_as_dz`
   *  :func:`make_pudl_tabl`
   *  :func:`lazy_import`

*  Created :mod:`etoolbox.utils.logging_utils` with helpers to setup and format loggers
   in a more performant and structured way based on
   `mCoding suggestion <https://www.youtube.com/watch?v=9L77QExPmI0>`_. Also replaced
   module-level loggers with library-wide logger and removed logger configuration from
   ``etoolbox`` because it is a library. This requires Python>=3.12.
*  Minor performance improvements to :meth:`.DataZip.keys` and :meth:`.DataZip.__len__`.
*  Fixed links to docs for :mod:`polars`, :mod:`plotly`, :mod:`platformdirs`,
   :mod:`fsspec`, and :mod:`pudl`. At least in theory.
*  Work toward benchmarks for :class:`.DataZip` vs :mod:`pickle`.
*  Optimization in :meth:`.DataZip.__getitem__` for reading a single value from a nested
   structure without decoding all enclosing objects, we use :func:`isinstance` and
   :meth:`dict.get` rather than try/except to handle non-dict objects and missing keys.
*  New CLI utility ``pudl-table-rename`` that renames PUDL tables in a set of files to
   the new names used by PUDL.
*  Allow older versions of :mod:`polars`, this is a convenience for some other projects
   that have not adapted to >=1.0 changes but we do not test against older versions.


Bug Fixes
^^^^^^^^^
*  Fixed a bug where ``etoolbox`` could not be used if ``tqdm`` was not installed. As
   it is an optional dependency, :mod:`._optional` should be able to fully address that
   issue.
*  Fixed a bug where import of :func:`typing.override` in
   :mod:`etoolbox.utils.logging_utils` broke compatibility with Python 3.11 since the
   function was added in 3.12.

.. _release-v0-2-0:

---------------------------------------------------------------------------------------
0.2.0 (2024-02-28)
---------------------------------------------------------------------------------------


*  Complete redesign of system internals and standardization of the data format. This
   resulted in a couple key improvements:

   *  **Performance** Decoding is now lazy, so structures and objects are only
      rebuilt when they are retrieved, rather than when the file is opened. Encoding is
      only done once, rather than once to make sure it will work, and then
      again when the data is written on close. Further, the correct encoder/decoder is
      selected using :class:`dict` lookups rather than chains of :func:`isinstance`.
   *  **Data Format** Rather than a convoluted system to flatten the object
      hierarchy, we preserve the hierarchy in the ``__attributes__.json`` file. We also
      provide encoders and decoders that allows all Python builtins as well as other
      types to be stored in ``json``. Any data that cannot be encoded to ``json`` is
      saved elsewhere and the entry in ``__attributes__.json`` contains a pointer to
      where the data is actually stored. Further, rather than storing some metadata in
      ``__attributes__.json`` and some elsewhere, now **all** metadata is stored
      alongside the data or pointer in ``__attributes__.json``.
   *  **Custom Classes** We no longer save custom objects as their own
      :class:`.DataZip`. Their location in the object hierarchy is preserved with a
      pointer and associated metadata. The object's state is stored separately in a
      hidden key, ``__state__`` in ``__attributes__.json``.
   *  **References** The old format stored every object as many times as it
      was referenced. This meant that objects could be stored multiple times and when
      the hierarchy was recreated, these objects would be copies. The new process for
      storing custom classes, :class:`pandas.DataFrame`, :class:`pandas.Series`, and
      :class:`numpy.array` uses :func:`id` to make sure we only store data once and
      that these relationships are recreated when loading data from a :class:`.DataZip`.
   *  **API** :class:`.DataZip` behaves a little like a :class:`dict`. It
      has :meth:`.DataZip.get`, :meth:`.DataZip.items`, and :meth:`.DataZip.keys` which
      do what you would expect. It also implements dunder methods to allow membership
      checking using ``in``, :func:`len`, and subscripts to get and set items (i.e.
      ``obj[key] = value``) these all also behave as you would expect, except that
      setting an item raises a :class:`KeyError` if the key is already in use.
      One additional feature with lookups is that you can provide multiple keys which
      are looked up recursively allowing efficient access to data in nested structures.
      :meth:`.DataZip.dump` and :meth:`.DataZip.load` are static methods that allow you
      to directly save and load an object into a :class:`.DataZip`, similar to
      :func:`pickle.dump` and :func:`pickle.load` except they handle opening and
      closing the file as well. Finally, :meth:`.DataZip.replace` is a little like
      :meth:`typing.NamedTuple._replace`; it copies the contents of one
      :class:`.DataZip` into a new one, with select keys replaced.

*  Added dtype metadata for :mod:`pandas` objects as well as ability to ignore that
   metadata to allow use of ``pyarrow`` dtypes.
*  Switching to use :mod:`ujson` rather than the standard library version for
   performance.
*  Added optional support for :class:`polars.DataFrame`, :class:`polars.LazyFrame`, and
   :class:`polars.Series` in :class:`.DataZip`.
*  Added :class:`.PretendPudlTabl` when passed as the ``klass`` argument to
   :meth:`.DataZip.load`, it allows accessing the dfs in a zipped :class:`pudl.PudlTabl`
   as you would normally but avoiding the :mod:`pudl` dependency.
*  Code cleanup along with adoption of `ruff <https://github.com/charliermarsh/ruff>`_
   and removal of bandit, flake8, isort, etc.
*  Added :func:`.lazy_import` to lazily import or proxy a module, inspired by
   :mod:`polars.dependencies.lazy_import`.
*  Created tools for proxying :class:`pudl.PudlTabl` to provide access to cached PUDL
   data without requiring that :mod:`pudl` is installed, or at least imported. The
   process of either loading a :class:`.PretendPudlTabl` from cache, or creating and
   then caching a :class:`pudl.PudlTabl` is handled by :func:`.make_pudl_tabl`.
*  Copied a number of helper functions that we often use  from :mod:`pudl.helpers` to
   :mod:`.pudl_helpers` so they can be used without installing or importing :mod:`pudl`.
*  Added a very light adaptation of the
   `python-remotezip <https://github.com/gtsystem/python-remotezip>`_ package to access
   files within a zip archive without downloading the full archive.
*  Updates to :class:`.DataZip` encoding and decoding of :class:`pandas.DataFrame` so
   they work with :mod:`pandas` version 2.0.0.
*  Updates to :func:`.make_pudl_tabl` and associated functions and classes so that it
   works with new and changing aspects of :class:`pudl.PudlTabl`, specifically those
   raised in
   `catalyst#2503 <https://github.com/orgs/catalyst-cooperative/discussions/2503>`_.
   Added testing for full :func:`.make_pudl_tabl` functionality.
*  Added to :func:`.get_pudl_table` which reads a table from a ``pudl.sqlite`` that is
   stored where it is expected.
*  Added support for :class:`polars.DataFrame`, :class:`polars.LazyFrame`, and
   :class:`polars.Series` to :func:`etoolbox.utils.testing.assert_equal`.
*  :class:`plotly.Figure` are now stored as pickles so they can be recreated.
*  Updates to :func:`.get_pudl_sql_url` so that it doesn't require
   PUDL environment variables or config files if the sqlite is at
   ``pudl-work/output/pudl.sqlite``, and tells the user to put the sqlite there if the
   it cannot be found another way.
*  New :func:`.conform_pudl_dtypes` function that casts PUDL columns to
   the dtypes used in :class:`PudlTabl`, useful when loading tables from a sqlite that
   doesn't preserve all dtype info.
*  Added :func:`ungzip` to help with un-gzipping ``pudl.sqlite.gz`` and now using the
   gzipped version in tests.
*  Switching two cases of ``with suppress...`` to ``try - except - pass`` in
   :class:`.DataZip` to take advantage of zero-cost exceptions.
*  **Deprecations** these will be removed in the next release along with supporting
   infrastructure:

   * :func:`.lazy_import` and the rest of the :mod:`.lazy_import` module.
   *  ``PUDL_DTYPES``, use :func:`.conform_pudl_dtypes` instead.
   *  :func:`.make_pudl_tabl`, :class:`.PretendPudlTablCore`,
      :class:`.PretendPudlTablCore`; read tables directly from the sqlite:

      .. code-block:: python

         import pandas as pd
         import sqlalchemy as sa

         from etoolbox.utils.pudl import get_pudl_sql_url, conform_pudl_dtypes

         pd.read_sql_table(table_name, sa.create_engine(get_pudl_sql_url())).pipe(
              conform_pudl_dtypes
          )


      .. code-block:: python

          import polars as pl

          from etoolbox.utils.pudl import get_pudl_sql_url

          pl.read_database("SELECT * FROM table_name", get_pudl_sql_url())



Bug Fixes
^^^^^^^^^
*  Allow :class:`typing.NamedTuple` to be used as keys in a :class:`dict`, and a
   :class:`collections.defaultdict`.
*  Fixed a bug in :func:`.make_pudl_tabl` where creating and caching a new
   :class:`pudl.PudlTabl` would fail to load the PUDL package.
*  Fixed a bug where attempting to retrieve an empty :class:`pandas.DataFrame` raised
   an :class:`IndexError` when ``ignore_pd_dtypes`` is ``False``.
*  Updated the link for the PUDL database.

Known Issues
^^^^^^^^^^^^
*  Some legacy :class:`.DataZip` files cannot be fully read, especially those with
   nested structures and custom classes.
*  :class:`.DataZip` ignores :func:`functools.partial` objects, at least in most dicts.

.. _release-v0-1-0:

---------------------------------------------------------------------------------------
0.1.0 (2023-02-27)
---------------------------------------------------------------------------------------

What's New?
^^^^^^^^^^^
*  Migrating :class:`.DataZip` from
   `rmi.dispatch <https://github.com/rmi-electricity/dispatch>`_ where it didn't really
   belong. Also added additional functionality including recursive writing and reading
   of :class:`list`, :class:`dict`, and :class:`tuple` objects.
*  Created :class:`.IOMixin` and :class:`IOWrapper` to make it easier to add
   :class:`.DataZip` to other classes.
*  Migrating :func:`.compare_dfs` from the Hub.
*  Updates to :class:`.DataZip`, :class:`.IOMixin`, and :class:`IOWrapper` to better
   better manage attributes missing from original object or file representation of
   object. Including ability to use differently organized versions of
   :class:`.DataZip`.
*  Clean up of :class:`.DataZip` internals, both within the object and in laying out
   files. Particularly how metadata and attributes are stored. Added
   :meth:`.DataZip.readm` and :meth:`.DataZip.writem` to read and write additional
   metadata not core to :class:`.DataZip`.
*  Added support for storing :class:`numpy.array` objects in :class:`.DataZip` using
   :func:`numpy.load` and :func:`numpy.save`.
*  :class:`.DataZip` now handles writing attributes and metadata using
   :meth:`.DataZip.close` so :class:`.DataZip` can now be used with or without a
   context manager.
*  Added :func:`.isclose`, similar to :func:`numpy.isclose` but allowing comparison
   of arrays containing strings, especially useful with :class:`pandas.Series`.
*  Added a module :mod:`etoolbox.utils.match` containing the helpers Raymond Hettinger
   demonstrated in his `talk <https://www.youtube.com/watch?v=ZTvwxXL37XI>`_ at PyCon
   Italia for using Python's ``case``/``match`` syntax.
*  Added support for Python 3.11.
*  Added support for storing :mod:`plotly` figures as ``pdf`` in :class:`.DataZip`.
   :meth:`.DataZip.close` so :class:`.DataZip` can now be used with or without a
   context manager.
*  Added support for checking whether a file or attribute is stored in
   :class:`.DataZip` using :meth:`.DataZip.__contains__`, i.e. using Python's ``in``.
*  Added support for subscript-based, getting and setting data in :class:`.DataZip`.
*  Custom Python objects can be serialized with :class:`.DataZip` if they implement
   ``__getstate__`` and ``__setstate__``, or can be serialized using the default
   logic described in :meth:`object.__getstate__`. That default logic is now
   implemented in :meth:`.DataZip.default_getstate` and
   :meth:`.DataZip.default_setstate`. This replaces the use of ``to_file``
   and ``from_file`` by :class:`.DataZip`. :class:`.IOMixin` has been updated
   accordingly.
*  Added static methods :meth:`.DataZip.dump` and :meth:`.DataZip.load` for
   serializing a single Python object, these are designed to be similar to how
   :func:`pickle.dump` and :func:`pickle.load` work.
*  Removing :class:`.IOWrapper`.
*  Added a :meth:`.DataZip.replace` that copies the contents of an old
   :class:`.DataZip` into a new copy of it after which you can add to it.
*  Extended JSON encoding / decoding to process an expanded set of builtins,
   standard library, and other common objects including :class:`tuple`, :class:`set`,
   :class:`frozenset`, :class:`complex`, :class:`typing.NamedTuple`,
   :class:`datetime.datetime`, :class:`pathlib.Path`, and :class:`pandas.Timestamp`.
*  Adding centralized testing helpers.
*  Added a subclass of ``PudlTabl`` that adds back ``__getstate__`` and
   ``__setstate__`` to enable caching, this caching will not work for tables that are
   not stored in the object which will be an increasing portion of tables as discussed
   `here <https://github.com/orgs/catalyst-cooperative/discussions/2503>`_.


Bug Fixes
^^^^^^^^^
*  Fixed an issue where a single column :class:`pandas.DataFrame` was recreated
   as a :class:`pandas.Series`. Now this should be backwards compatible by applying
   :class:`pandas.DataFrame.squeeze` if object metadata is not available.
*  Fixed a bug that prevented certain kinds of objects from working properly under
   3.11.
*  Fixed an issue where the name for a :class:`pandas.Series` might get mangled or
   changed.


Known Issues
^^^^^^^^^^^^
*  Recipe system is fragile and bespoke, there really should be a better way...
*  :class:`tuple` nested inside other objects may be returned as :class:`list`.
