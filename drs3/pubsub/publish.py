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

"""
Publish asynchronous topics
"""

import json
from pathlib import Path

import pika
from ghga_service_chassis_lib.pubsub import AmqpTopic

HERE = Path(__file__).parent.resolve()


def publish_topic(host, port, topic_name, message):
    """
    Publishes a message to a specified topic
    """

    # read json schema:
    with open(f"{HERE}/{topic_name}.json", "r", encoding="utf-8") as schema_file:
        message_schema = json.load(schema_file)

    # create a topic object:
    topic = AmqpTopic(
        connection_params=pika.ConnectionParameters(host=host, port=port),
        topic_name=topic_name,
        service_name="drs3",
        json_schema=message_schema,
    )

    topic.publish(message)