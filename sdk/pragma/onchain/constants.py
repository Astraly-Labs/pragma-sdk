from typing import Dict, List

from pragma.onchain.types import ContractAddresses, Network


CHAIN_IDS: Dict[Network, int] = {
    "devnet": 23448594291968334,
    "mainnet": 23448594291968334,
    "fork_devnet": 23448594291968334,
    "sepolia": 393402133025997798000961,
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
        1035964020232444284030697086969999610062982650901949616270651804992179237909,
        1202089834814778579992154020333959781277480478747022471664051891421849487195,
    ),
    "sepolia": ContractAddresses(
        764259049439565269590387705502051444787910047543242149334355727309682685773,
        1526899943909931281366530977873767661043021921869578496106478460498705257242,
    ),
}


RANDOMNESS_REQUEST_EVENT_SELECTOR = (
    "0xe3e1c077138abb6d570b1a7ba425f5479b12f50a78a72be680167d4cf79c48"
)