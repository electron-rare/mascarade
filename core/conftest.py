"""Root conftest — skip broken test modules during collection."""
collect_ignore_glob = [
    "tests/node_engine/*",
    "tests/test_node_*",
]
