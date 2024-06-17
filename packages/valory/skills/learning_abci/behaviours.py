# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains round behaviours of LearningAbciApp."""

from abc import ABC
from typing import Generator, Set, List, Type, cast, Optional, Dict, Any, Tuple, Union
from hexbytes import HexBytes
from packages.valory.contracts.portfolio_manager.contract import PortfolioManagerContract
from packages.valory.contracts.erc20.contract import ERC20
from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation
)
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.learning_abci.models import Params, SharedState
from packages.valory.skills.learning_abci.payloads import (
    APICheckPayload,
    DecisionMakingPayload,
    TxPreparationPayload,
)
from packages.valory.skills.learning_abci.rounds import (
    APICheckRound,
    DecisionMakingRound,
    LearningAbciApp,
    SynchronizedData,
    TxPreparationRound,
    Event
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
import json

HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
TX_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"
SELL = "sell"
BUY = "buy"
class LearningBaseBehaviour(BaseBehaviour, ABC):  # pylint: disable=too-many-ancestors
    """Base behaviour for the learning_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def local_state(self) -> SharedState:
        """Return the state."""
        return cast(SharedState, self.context.state)


class APICheckBehaviour(LearningBaseBehaviour):  # pylint: disable=too-many-ancestors
    """APICheckBehaviour"""

    matching_round: Type[AbstractRound] = APICheckRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            price = yield from self.get_price()
            self.context.logger.info(f"PRICE RETRIEVED FROM COINGECKO API- {price}") 
            
            #dummy data
            rebalancing_rules = {
                "user_id": "user123",
                "rules": {
                    "thresholds": {
                        "deviation": 0.05
                    },
                    "frequency": "weekly",
                    "no_trade_tokens": ["XYZ"]
                }
            }

            ipfs_hash = yield from self.send_to_ipfs(
                "rebalancing-rules.json", 
                {"rebalancing-rules" : rebalancing_rules}, 
                filetype=SupportedFiletype.JSON
            )

            self.context.logger.info(f"IPFS HASH- {ipfs_hash}")
            payload = APICheckPayload(sender=sender, price=price, ipfs_hash=ipfs_hash)
  
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_price(self) -> Generator[None, None, Optional[int]]:

        response = yield from self.get_http_response(
            method="GET",
            url= self.params.coingecko_price_template,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-cg-demo-api-key": self.params.coingecko_api_key,
            },
        )

        if(response.status_code != 200):
            self.context.logger.error(f"Error in fetching the price with status code {response.status_code}")

        decoded_response = response.body

        try:
            response_data = json.loads(decoded_response)
            price = response_data['autonolas']['inr']
            return price
        except json.JSONDecodeError:
            self.context.logger.error("APICHECK_BEHAVIOUR says: Could not parse the response body!") 
            return None 
    
class DecisionMakingBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local(): 
            if self.synchronized_data.price == None:
                event = Event.ERROR.value
            #implement custom logic to check the condition for portfolio rebalance
            elif self.synchronized_data.price > self.params.decision_threshold:
                event= Event.TRANSACT.value
            else:
                event= Event.DONE.value

            sender = self.context.agent_address
            payload = DecisionMakingPayload(sender=sender, event=event)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

class TxPreparationBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """TxPreparationBehaviour"""

    matching_round: Type[AbstractRound] = TxPreparationRound
    ETHER_VALUE = 0
    MULTISEND_ADDRESS = "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761"
    SELLER_ADDRESS = "0xBd748eeb04623605BC1566b3F7F7f3e904f9Fe6D"
    BUYER_ADDRESS = "0x82a05d94630479e409ee235E8A8C5B65c7f7560e"

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            update_portfolio_payload = yield from self.get_portfolio_update()

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            payload = TxPreparationPayload(
                self.context.agent_address,
                update_portfolio_payload
            )
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_portfolio_update(self) -> Generator[None, None, str]:
        """
        Check whether sell or buy txn needs to be made
        If sell, then bundle approve txn with that
        """

        # We can get the rebalancing rules from IPFS and then make an informed decision
        rules = yield from self.get_from_ipfs(
            self.synchronized_data.ipfs_hash, filetype=SupportedFiletype.JSON
        )
        self.context.logger.info(f"DATA RETRIEVED FROM IPFS {rules}")
        
        token = self.params.portfolio_token

        (decision, amount) = yield from self._get_token_rebalance_amount(token)
        self.context.logger.info(f" PORTFOLIO REBALANCE DECISION: {decision}")

        if decision is None:
            return "{}"
        
        if decision is BUY:
            safe_txn = yield from self._build_buy_txn(amount, token)
            return safe_txn
        
        elif decision is SELL:
            transactions = yield from self._build_approve_and_buy_txns(amount, token)
            if transactions is None:
                return "{}"
            
            payload_data = yield from self._get_multisend_tx(transactions)
            self.context.logger.info(f"MULTISEND TRANSACTIONS {payload_data}")
            if payload_data is None:
                return "{}"
            return payload_data

    def _get_token_rebalance_amount(self, token:str) -> Generator[None, None, Union[int, Tuple[str, int]]]:
        #check the deviation in portfolio for the token and based on that take a decision
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_id=str(PortfolioManagerContract.contract_id),
            contract_callable="get_check_deviation_tx",
            contract_address=self.params.portfolio_manager_contract_address,
            token = token
        )

        deviation = response.state.body['data']       
        self.context.logger.info(f"DEVIATION IN TOKEN PERCENTAGE RETRIEVED FROM CONTRACT: {deviation}")
        amount = 10**18

        #We can implement logic to get the amount of token based that we need to sell or buy based on the deviation
        if deviation is None:
            return ()     
        if deviation < 0:
            return (BUY, amount)
        else:
            return (SELL, amount)

    
    def _build_buy_txn(self, amount:int, token:str) -> Generator[None, None, str]:

        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_id=str(PortfolioManagerContract.contract_id),
            contract_callable="get_simulate_buy_tx",
            contract_address=self.params.portfolio_manager_contract_address,
            token=token,
            amount=amount,
            buyer=self.BUYER_ADDRESS
        )

        self.context.logger.info(f"BUY TXN: {response}")

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"TxPreparationBehaviour says: Couldn't get tx data for the txn. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        data_str = cast(str, response.state.body["data"])[2:]
        txn = bytes.fromhex(data_str)

        if txn is None:
            return "{}"

        safe_tx_hash = yield from self._get_safe_tx_hash(
            txn,
            self.params.portfolio_manager_contract_address
        )

        if safe_tx_hash is None:
            return "{}"

        payload_data = hash_payload_to_hex(
            safe_tx_hash=safe_tx_hash,
            to_address=self.params.portfolio_manager_contract_address,
            ether_value=self.ETHER_VALUE,  # we don't send any eth
            safe_tx_gas=SAFE_GAS,
            data=txn,
        )

        return payload_data
    
    def _build_sell_txn(self, amount:int, token:str) -> Generator[None, None, Optional[bytes]]:
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_id=str(PortfolioManagerContract.contract_id),
            contract_callable="get_simulate_sell_tx",
            contract_address=self.params.portfolio_manager_contract_address,
            token=token,
            amount=amount,
            seller=self.SELLER_ADDRESS
        )

        self.context.logger.info(f"SELL TXN: {response}")

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"TxPreparationBehaviour says: Couldn't get tx data for the txn. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        data_str = cast(str, response.state.body["data"])[2:]
        data = bytes.fromhex(data_str)
        return data
    
    def _build_approve_txn(self, amount:int, token:str) -> Generator[None, None, Optional[bytes]]:
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_id=str(ERC20.contract_id),
            contract_callable="build_approval_tx",
            contract_address=token,
            spender=self.params.portfolio_manager_contract_address,
            amount=amount
        )

        self.context.logger.info(f"APPROVE TXN: {response}")

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"TxPreparationBehaviour says: Couldn't get tx data for the txn. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        data_str = cast(str, response.state.body["data"])[2:]
        data = bytes.fromhex(data_str)
        return data
    
    def _build_approve_and_buy_txns(self, amount:int, token:str) -> Generator[None, None, Optional[List[bytes]]]:
        transactions: List[bytes] = []

        approve_tx_data = yield from self._build_approve_txn(amount, token)
        if approve_tx_data is None:
                return None      
        transactions.append(approve_tx_data)

        sell_tx_data = yield from self._build_sell_txn(amount, token)
        if sell_tx_data is None:
                return None      
        transactions.append(sell_tx_data)

        return transactions
    
    def _get_safe_tx_hash(self, data: bytes, to_address: str, is_multisend: bool = False) -> Generator[None, None, Optional[str]]:
        """
        Prepares and returns the safe tx hash.

        This hash will be signed later by the agents, and submitted to the safe contract.
        Note that this is the transaction that the safe will execute, with the provided data.

        :param data: the safe tx data. This is the data of the function being called, in this case `updateWeightGradually`.
        :return: the tx hash
        """
        contract_api_kwargs = {
            "performative": ContractApiMessage.Performative.GET_STATE,  # type: ignore
            "contract_address": self.synchronized_data.safe_contract_address,  # the safe contract address
            "contract_id": str(GnosisSafeContract.contract_id),
            "contract_callable": "get_raw_safe_transaction_hash",
            "to_address": to_address,
            "value": self.ETHER_VALUE,
            "data": data,
            "safe_tx_gas": SAFE_GAS,
        }
        
        if is_multisend:
            contract_api_kwargs["operation"] = SafeOperation.DELEGATE_CALL.value

        response = yield from self.get_contract_api_response(**contract_api_kwargs)

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"TxPreparationBehaviour says: Couldn't get safe hash. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        # strip "0x" from the response hash
        tx_hash = cast(str, response.state.body["tx_hash"])[2:]
        return tx_hash

    def _get_multisend_tx(self, txs: List[bytes])-> Generator[None, None, Optional[str]]:
        """Given a list of transactions, bundle them together in a single multisend tx."""
        multi_send_txs = []

        multi_send_approve_tx = self._to_multisend_format(txs[0], self.params.portfolio_token)
        multi_send_txs.append(multi_send_approve_tx)

        multi_send_sell_tx = self._to_multisend_format(txs[1], self.params.portfolio_manager_contract_address)
        multi_send_txs.append(multi_send_sell_tx)

        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.MULTISEND_ADDRESS,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=multi_send_txs,
        )

        self.context.logger.info(f"PREPARED MULTISEND TXN:{response}")

        if response.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Couldn't compile the multisend tx. "
                f"Expected response performative {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        # strip "0x" from the response
        multisend_data_str = cast(str, response.raw_transaction.body["data"])[2:]
        tx_data = bytes.fromhex(multisend_data_str)
        tx_hash = yield from self._get_safe_tx_hash(tx_data, self.MULTISEND_ADDRESS, is_multisend=True)
        
        if tx_hash is None:
            return None

        payload_data = hash_payload_to_hex(
            safe_tx_hash=tx_hash,
            ether_value=self.ETHER_VALUE,
            safe_tx_gas=SAFE_GAS,
            operation=SafeOperation.DELEGATE_CALL.value,
            to_address=self.MULTISEND_ADDRESS,
            data=tx_data,
        )
        return payload_data

    def _to_multisend_format(self, single_tx: bytes, to_address) -> Dict[str, Any]:
        """This method puts tx data from a single tx into the multisend format."""
        multisend_format = {
            "operation": MultiSendOperation.CALL,
            "to": to_address,
            "value": self.ETHER_VALUE,
            "data": HexBytes(single_tx),
        }
        return multisend_format   
class LearningRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""

    initial_behaviour_cls = APICheckBehaviour
    abci_app_cls = LearningAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore
        APICheckBehaviour,
        DecisionMakingBehaviour,
        TxPreparationBehaviour,
    ]
