#  Drakkar-Software OctoBot
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import copy
import time
import aiohttp

from config import PROJECT_NAME, LONG_VERSION
from octobot.evaluator_factory import EvaluatorFactory
from octobot.exchange_factory import ExchangeFactory
from octobot.initializer import Initializer
from octobot.interface_factory import InterfaceFactory
from octobot.task_manager import TaskManager
from octobot_commons.enums import MarkdownFormat
from octobot_commons.logging.logging_util import get_logger
from octobot_evaluators.constants import CONFIG_EVALUATOR
from octobot_notifications.api.notification import send_notification, create_notification
from octobot_trading.constants import CONFIG_TRADING_TENTACLES

"""Main OctoBot class:
- Create all indicators and thread for each cryptocurrencies in config """


class OctoBot:
    """
    Constructor :
    - Load configs
    """

    def __init__(self, config, ignore_config=False, reset_trading_history=False):
        self.start_time = time.time()
        self.config = config
        self.reset_trading_history = reset_trading_history
        self.startup_config = copy.deepcopy(self.config)
        self.edited_config = copy.deepcopy(self.config)

        # Used to know when OctoBot is ready to answer in APIs
        self.initialized = False

        # tools: used for alternative operations on a bot on the fly (ex: backtesting started from web interface)
        # self.tools = {
        #     BOT_TOOLS_BACKTESTING: None,
        #     BOT_TOOLS_STRATEGY_OPTIMIZER: None,
        #     BOT_TOOLS_RECORDER: None,
        # }

        # unique aiohttp session: to be initialized from getter in a task
        self._aiohttp_session = None

        # metrics if enabled
        self.metrics_handler = None

        # Logger
        self.logger = get_logger(self.__class__.__name__)

        self.initializer = Initializer(self)
        self.task_manager = TaskManager(self)
        self.exchange_factory = ExchangeFactory(self, ignore_config=ignore_config)
        self.evaluator_factory = EvaluatorFactory(self)
        self.interface_factory = InterfaceFactory(self)

        self.async_loop = None

    async def initialize(self):
        await self.initializer.create()
        self.task_manager.init_async_loop()
        await self.task_manager.start_tools_tasks()
        await self.evaluator_factory.initialize()
        await self.exchange_factory.create()
        await self.evaluator_factory.create()
        await self.interface_factory.create()
        await self.interface_factory.start_interfaces()
        await self._post_initialize()

    async def _post_initialize(self):
        self.initialized = True

        # update startup_config and edited_config now that config contains all necessary info
        # (tentacles config added in initialize)
        # this might be temporary waiting for tentacle manager refactor
        for config_element in (CONFIG_EVALUATOR, CONFIG_TRADING_TENTACLES):
            self.startup_config[config_element] = copy.deepcopy(self.config[config_element])
            self.edited_config[config_element] = copy.deepcopy(self.config[config_element])

        await send_notification(create_notification(f"{PROJECT_NAME} {LONG_VERSION} is starting ...",
                                                    markdown_format=MarkdownFormat.ITALIC))

    def run_in_main_asyncio_loop(self, coroutine):
        return self.task_manager.run_in_main_asyncio_loop(coroutine)

    def set_watcher(self, watcher):
        self.task_manager.watcher = watcher

    def get_aiohttp_session(self):
        if self._aiohttp_session is None:
            self._aiohttp_session = aiohttp.ClientSession()
        return self._aiohttp_session