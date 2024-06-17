
from typing import Any, Dict, List, Optional, cast

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea_ledger_ethereum import LedgerApi

PUBLIC_ID = PublicId.from_str("valory/portfolio_manager:0.1.0")

class PortfolioManagerContract(Contract):
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
    def get_simulate_buy_tx(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        token: str,
        amount: int,
        buyer: str
    ) -> Dict[str, Any]:
        contract_instance = cls.get_instance(ledger_api, contract_address)
        checksumed_token = ledger_api.api.to_checksum_address(token)
        checksumed_buyer = ledger_api.api.to_checksum_address(buyer)
        tx_data = contract_instance.encodeABI(
            fn_name="simulateBuy",
            args=[
                checksumed_token,
                amount,
                checksumed_buyer
            ],
        )
        
        return dict(
            data=tx_data,
        )
    
    @classmethod
    def get_simulate_sell_tx(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        token: str,
        amount: int,
        seller: str
    ) -> Dict[str, Any]:
        contract_instance = cls.get_instance(ledger_api, contract_address)
        checksumed_token = ledger_api.api.to_checksum_address(token)
        checksumed_seller = ledger_api.api.to_checksum_address(seller)
        tx_data = contract_instance.encodeABI(
            fn_name="simulateSell",
            args=[
                checksumed_token,
                amount,
                checksumed_seller
            ],
        )
        
        return dict(
            data=tx_data,
        )
        
    @classmethod
    def get_check_deviation_tx(
        cls,
        ledger_api: LedgerApi,
        contract_address: str,
        token: str
    ) -> Dict[str, Any]:
        contract_instance = cls.get_instance(ledger_api, contract_address)
        checksumed_token = ledger_api.api.to_checksum_address(token)
        deviation = contract_instance.functions.checkDeviation(checksumed_token).call()
        return dict(data=deviation)