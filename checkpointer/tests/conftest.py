# This is needed for importing fixtures from `fixtures` directory
pytest_plugins = [
    "tests.integration.fixtures.account",
    "tests.integration.fixtures.contracts",
    "tests.integration.fixtures.devnet",
    "tests.integration.fixtures.clients",
    "tests.integration.fixtures.misc",
]
