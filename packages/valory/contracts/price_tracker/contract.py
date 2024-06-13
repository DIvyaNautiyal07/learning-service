
import logging
from typing import Any, Dict, List, Optional, cast

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea_ledger_ethereum import EthereumApi, LedgerApi
from web3.types import BlockIdentifier, Nonce, TxParams, Wei

PUBLIC_ID = PublicId.from_str("valory/price_tracker:0.1.0")

class PriceTrackerContract(Contract):
    contract_id = PUBLIC_ID
    @classmethod
    def get_raw_transaction(
        cls, ledger_api: LedgerApi, contract_address: str, **kwargs: Any
    ) -> Optional[JSONLike]:
        """Get the Safe transaction."""
        raise NotImplementedError

    @classmethod
    def get_raw_message(
        cls, ledger_api: LedgerApi, contract_address: str, **kwargs: Any
    ) -> Optional[bytes]:
        """Get raw message."""
        raise NotImplementedError

    @classmethod
    def get_state(
        cls, ledger_api: LedgerApi, contract_address: str, **kwargs: Any
    ) -> Optional[JSONLike]:
        """Get state."""
        raise NotImplementedError
    
    @classmethod
    def get_update_price_tx(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        price: int,
    ) -> Dict[str, Any]:
        contract_instance = cls.get_instance(ledger_api, contract_address)
        tx_data = contract_instance.encodeABI(
            fn_name="updatePrice",
            args=[
                price
            ],
        )
        
        return dict(
            data=tx_data,
        )