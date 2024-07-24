import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--net",
        action="store",
        default="devnet",
        help="Network to run tests on, one of: " "`mainnet`, `sepolia`, `devnet`",
    )


@pytest.fixture(scope="function")
def network(pytestconfig, run_devnet: str) -> str:
    """
    Returns network address depending on the --net parameter.
    """
    net = pytestconfig.getoption("--net")
    net_address = {
        "devnet": run_devnet,
        "sepolia": "sepolia",
    }

    return net_address[net]


def pytest_collection_modifyitems(config, items):
    if config.getoption("--net") == "all":
        return

    run_sepolia = config.getoption("--net") == "sepolia"
    run_devnet = config.getoption("--net") == "devnet"
    for item in items:
        runs_on_sepolia = "run_on_sepolia" in item.keywords
        runs_on_devnet = "run_on_devnet" in item.keywords
        should_not_run = (runs_on_devnet and not run_devnet) or (
            runs_on_sepolia and not run_sepolia
        )
        if should_not_run:
            item.add_marker(pytest.mark.skip())
