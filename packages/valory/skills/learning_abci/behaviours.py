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
from typing import Generator, Set, Type, cast, Optional

from packages.valory.contracts.price_tracker.contract import PriceTrackerContract
from packages.valory.contracts.erc20.contract import ERC20
from packages.valory.contracts.gnosis_safe.contract import GnosisSafeContract
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

import json

HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
TX_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"


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
            payload = APICheckPayload(sender=sender, price=price)
            self.context.logger.info(f"PRICE RETRIEVED FROM COINGECKO API- {price}")   

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
            self.context.logger.info(f"JSON RESPONSE: {response_data}")
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
            elif self.synchronized_data.price > 160:
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

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            safe_tx = yield from self.build_transfer_txn()
            # safe_tx = yield from self.build_wxdai_transfer_txn()
            # safe_tx = yield from self.build_update_price_txn()

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            payload = TxPreparationPayload(
                self.context.agent_address,
                safe_tx
            )
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def build_transfer_txn(self) -> Generator[None, None, Optional[str]]:
        calldata = {"value": 10**18, "to_address": self.params.transfer_target_address}

        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address = self.synchronized_data.safe_contract_address,
            contract_id= str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            safe_tx_gas = SAFE_GAS,
            data=b"0x",
            **calldata
        )

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"TxPreparationBehaviour says: Couldn't get safe hash. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return "{}"
        
        self.context.logger.info(f"PREPARED SAFE TXN:{response}")

        safe_tx_hash = cast(str, response.state.body["tx_hash"])[2:]

        tx_hash = hash_payload_to_hex(
            safe_tx_hash,
            calldata["value"],
            SAFE_GAS,
            calldata["to_address"],
            data=b"0x"
        )
        
        self.context.logger.info(f"FINAL TXN HASH:{tx_hash}")
        return tx_hash

    def build_wxdai_transfer_txn(self) -> Generator[None, None, str]:
        
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_id=str(ERC20.contract_id),
            contract_callable="build_transfer_tx",
            contract_address=self.params.wxdai_contract_address,
            to=self.params.transfer_target_address,
            amount=10**19
        )

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"TxPreparationBehaviour says: Couldn't get tx data for the txn. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        self.context.logger.info(f"UPDATE PRICE TX: {response}")
        data_str = cast(str, response.state.body["data"])[2:]
        txn = bytes.fromhex(data_str)

        self.context.logger.info(f"TxPreparationBehaviour says: TOKEN TRANSFER TX: {txn}")

        if txn is None:
            return "{}"

        safe_tx_hash = yield from self._get_safe_tx_hash(
            txn
        )

        if safe_tx_hash is None:
            return "{}"

        # params here need to match those in _get_safe_tx_hash()
        payload_data = hash_payload_to_hex(
            safe_tx_hash=safe_tx_hash,
            ether_value=self.ETHER_VALUE,  # we don't send any eth
            safe_tx_gas=SAFE_GAS,
            to_address=self.params.wxdai_contract_address,
            data=txn,
        )

        return payload_data
    
    def build_update_price_txn(self) -> Generator[None, None, str]:
        price = int(self.synchronized_data.price)

        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_id=str(PriceTrackerContract.contract_id),
            contract_callable="get_update_price_tx",
            contract_address=self.params.price_tracker_contract_address,
            price=price,
        )

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"TxPreparationBehaviour says: Couldn't get tx data for the txn. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        self.context.logger.info(f"UPDATE PRICE TX: {response}")

        data_str = cast(str, response.state.body["data"])[2:]
        txn = bytes.fromhex(data_str)

        if txn is None:
            return "{}"

        safe_tx_hash = yield from self._get_safe_tx_hash(
            txn
        )

        if safe_tx_hash is None:
            return "{}"

        # params here need to match those in _get_safe_tx_hash()
        payload_data = hash_payload_to_hex(
            safe_tx_hash=safe_tx_hash,
            ether_value=self.ETHER_VALUE,  # we don't send any eth
            safe_tx_gas=SAFE_GAS,
            to_address=self.params.wxdai_contract_address,
            data=txn,
        )

        return payload_data
    
    
    
    def _get_safe_tx_hash(self, data: bytes) -> Generator[None, None, Optional[str]]:
        """
        Prepares and returns the safe tx hash.

        This hash will be signed later by the agents, and submitted to the safe contract.
        Note that this is the transaction that the safe will execute, with the provided data.

        :param data: the safe tx data. This is the data of the function being called, in this case `updateWeightGradually`.
        :return: the tx hash
        """
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,  # the safe contract address
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.wxdai_contract_address,  # the contract the safe will invoke
            value=self.ETHER_VALUE,
            data=data,
            safe_tx_gas=SAFE_GAS,
        )
        self.context.logger.info(f"PREPARED SAFE TXN:{response}")

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


class LearningRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""

    initial_behaviour_cls = APICheckBehaviour
    abci_app_cls = LearningAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore
        APICheckBehaviour,
        DecisionMakingBehaviour,
        TxPreparationBehaviour,
    ]
