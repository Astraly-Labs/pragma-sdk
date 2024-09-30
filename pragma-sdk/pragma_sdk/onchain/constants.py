from typing import Dict, List
from starknet_py.net.models.chains import StarknetChainId

from pragma_sdk.common.utils import str_to_felt
from pragma_sdk.onchain.types import ContractAddresses, Network


CHAIN_IDS: Dict[Network, StarknetChainId] = {
    "devnet": StarknetChainId.MAINNET,
    "mainnet": StarknetChainId.MAINNET,
    "sepolia": StarknetChainId.SEPOLIA,
    "madara_test": 93395501017206423887893332,
}

CHAIN_ID_TO_NETWORK = {v: k for k, v in CHAIN_IDS.items()}

STARKSCAN_URLS: Dict[Network, str] = {
    "mainnet": "https://starkscan.co",
    "sepolia": "https://sepolia.starkscan.co",
}

RPC_URLS: Dict[Network, List[str]] = {
    "mainnet": [
        "https://starknet-mainnet.public.blastapi.io/rpc/v0_7",
    ],
    "sepolia": [
        "https://starknet-sepolia.public.blastapi.io/rpc/v0_7",
    ],
}

CONTRACT_ADDRESSES = {
    "mainnet": ContractAddresses(
        publisher_registry_address=1035964020232444284030697086969999610062982650901949616270651804992179237909,
        oracle_proxy_addresss=1202089834814778579992154020333959781277480478747022471664051891421849487195,
        summary_stats_address=2090067484320946173645263594661603017833855811144011943422870527090500064765,
    ),
    "sepolia": ContractAddresses(
        publisher_registry_address=764259049439565269590387705502051444787910047543242149334355727309682685773,
        oracle_proxy_addresss=1526899943909931281366530977873767661043021921869578496106478460498705257242,
        summary_stats_address=2384164285657453557205017005077409893704644163574788258484357745200820117852,
    ),
    "madara_test": ContractAddresses(
        publisher_registry_address=461356997534138225460795749068013349309509634922228310871652186075935126849,
        oracle_proxy_addresss=2598637178162175124540269278489155568057234289210572147052744598475407626026,
        summary_stats_address=0,
    ),
}


RANDOMNESS_REQUEST_EVENT_SELECTOR = (
    "0xe3e1c077138abb6d570b1a7ba425f5479b12f50a78a72be680167d4cf79c48"
)

DERIBIT_MERKLE_FEED_KEY = str_to_felt("DERIBIT_OPTIONS_MERKLE_ROOT")
