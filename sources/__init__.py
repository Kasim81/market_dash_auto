"""
sources package
===============
Per-source data providers for the macro-data pipeline.  Each submodule exposes
a small, consistent interface (library loader + snapshot fetcher + history
fetcher) with no CSV or Sheets side effects — those live in the root-level
coordinator scripts (fetch_macro_*.py).

The `base` submodule provides shared plumbing used by both source modules and
coordinators.
"""
