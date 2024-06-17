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

"""This module contains the shared state for the abci skill of LearningAbciApp."""

from typing import Any, List

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.learning_abci.rounds import LearningAbciApp


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = LearningAbciApp


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""
        self.coingecko_price_template = self._ensure(
            "coingecko_price_template", kwargs, str
        )
        self.coingecko_api_key = kwargs.get("coingecko_api_key", None)
        self.portfolio_token = self._ensure(
            "portfolio_token", kwargs, str
        )
        self.portfolio_manager_contract_address = self._ensure(
            "portfolio_manager_contract_address", kwargs, str
        )
        self.transfer_target_address = self._ensure(
            "transfer_target_address", kwargs, str
        )
        # UNABLE TO RESOLVE THE ERROR aea.exceptions.AEAEnforceError: 'multisend_address' of type '<class 'str'>' required, but it is not set in `models.params.args` of `skill.yaml` of `valory/learning_chained_abci:0.1.0`
        # self.multisend_address = self._ensure(
        #     "multisend_address", kwargs, str
        # )
        self.decision_threshold = self._ensure(
            "decision_threshold", kwargs, int
        )
        super().__init__(*args, **kwargs)
