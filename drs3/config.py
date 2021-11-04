# Copyright 2021 Universität Tübingen, DKFZ and EMBL
# for the German Human Genome-Phenome Archive (GHGA)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Config Parameter Modeling and Parsing"""

from functools import lru_cache

from ghga_service_chassis_lib.config import config_from_yaml
from ghga_service_chassis_lib.pubsub import PubSubConfigBase


@config_from_yaml(prefix="drs3")
class Config(PubSubConfigBase):
    """Config parameters and their defaults."""

    # config parameter needed for rabbitmq server
    # are inherited from PubSubConfigBase;


@lru_cache
def get_config():
    """Get runtime configuration."""
    return Config()