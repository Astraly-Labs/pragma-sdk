from pathlib import Path
from typing import Dict, List, Literal

from pydantic import HttpUrl

from pragma_sdk.common.configs.asset_config import ALL_ASSETS_CONFIGS, AssetConfig
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.pair import Pair


def find_repo_root(start_directory: Path) -> Path:
    """Finds the root directory of the repo by walking up the directory tree
    and looking for a known file at the repo root.
    """
    current_directory = start_directory
    while current_directory != current_directory.parent:  # Stop at filesystem root
        if (current_directory / "pyproject.toml").is_file():
            return current_directory
        current_directory = current_directory.parent
    raise ValueError("Repository root not found!")


current_file_directory = Path(__file__).parent
repo_root = find_repo_root(current_file_directory).parent

SUBMODULE_DIR = repo_root / "pragma-oracle"
CONTRACTS_COMPILED_DIR = SUBMODULE_DIR / "target/dev"
DEPLOYMENTS_DIR = SUBMODULE_DIR / "deployments"


U128_MAX = (1 << 128) - 1
U256_MAX = (1 << 256) - 1

NetworkName = Literal[
    "devnet",
    "mainnet",
    "sepolia",
]
Network = HttpUrl | NetworkName

RPC_URLS: Dict[Network, List[str]] = {
    "mainnet": [
        "https://starknet-mainnet.public.blastapi.io/rpc/v0_7",
    ],
    "sepolia": [
        "https://starknet-sepolia.public.blastapi.io/rpc/v0_7",
    ],
}


FEE_TOKEN_ADDRESS = "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7"


# ========= Accounts =============

DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS = (
    "0x260a8311b4f1092db620b923e8d7d20e76dedcc615fb4b6fdf28315b81de201"
)
DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY = "0xc10662b7b247c7cecf7e8a30726cff12"

TESTNET_ACCOUNT_PRIVATE_KEY = "0xc10662b7b247c7cecf7e8a30726cff12"
TESTNET_ACCOUNT_ADDRESS = "0x260a8311b4f1092db620b923e8d7d20e76dedcc615fb4b6fdf28315b81de201"

USD_ASSET_CONFIG = AssetConfig.from_ticker("USD")

CURRENCIES = [Currency.from_asset_config(asset) for asset in ALL_ASSETS_CONFIGS]
USD_PAIRS: List[Pair] = filter(
    lambda x: x is not None,
    [Pair.from_asset_configs(asset, USD_ASSET_CONFIG) for asset in ALL_ASSETS_CONFIGS],
)
