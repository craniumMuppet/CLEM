"""Deprecated compatibility plugin.

v2.29.2 no longer forces an immediate process exit after the pytest call phase,
because that could hide teardown and fixture-finalizer failures. The file
remains importable for old commands but deliberately registers no hooks.
"""
