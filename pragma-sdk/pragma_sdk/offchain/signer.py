from typing import List, Optional, Tuple

from starknet_py.net.signer.stark_curve_signer import StarkCurveSigner
from starknet_py.utils.typed_data import TypedData

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.types import DataTypes


def build_publish_message(
    entries: List[Entry], data_type: Optional[DataTypes] = DataTypes.SPOT
) -> TypedData:
    """
    Builds a typed data message to publish spot entries on the Pragma API.
    see https://community.starknet.io/t/snip-off-chain-signatures-a-la-eip712 for reference

    :param entries: List of SpotEntry objects
    """

    message = {
        # TODO: We want to update `revision` to `1` but that would require some changes
        # in the `pragma-node` repository - where we check the signature.
        # See: https://github.com/astraly-labs/pragma-sdk/issues/151
        "domain": {"name": "Pragma", "version": "1", "chainId": "1", "revision": "0"},
        "primaryType": "Request",
        "message": {
            "action": "Publish",
            "entries": Entry.serialize_entries(entries),
        },
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "version", "type": "felt"},
                {"name": "chainId", "type": "felt"},
                {"name": "revision", "type": "felt"},
            ],
            "Request": [
                {"name": "action", "type": "felt"},
                {"name": "entries", "type": "Entry*"},
            ],
            "Entry": [
                {"name": "base", "type": "Base"},
                {"name": "pair_id", "type": "felt"},
                {"name": "price", "type": "felt"},
                {"name": "volume", "type": "felt"},
            ],
            "Base": [
                {"name": "publisher", "type": "felt"},
                {"name": "source", "type": "felt"},
                {"name": "timestamp", "type": "felt"},
            ],
        },
    }
    if data_type == DataTypes.FUTURE:
        message["types"]["Entry"] += [  # type: ignore[index]
            {"name": "expiration_timestamp", "type": "felt"},
        ]

    return TypedData.from_dict(message)


class OffchainSigner:
    """
    Class used to sign messages for the Pragma API
    """

    def __init__(self, signer: StarkCurveSigner):
        self.signer = signer

    def sign_publish_message(
        self, entries: List[Entry], data_type: Optional[DataTypes] = DataTypes.SPOT
    ) -> Tuple[List[int], int]:
        """
        Sign a publish message

        :param entries: List of SpotEntry objects
        :return: Tuple containing the signature and the message hash
        """
        message = build_publish_message(entries, data_type)
        hash_ = message.message_hash(self.signer.address)
        sig = self.signer.sign_message(message, self.signer.address)
        return sig, hash_
