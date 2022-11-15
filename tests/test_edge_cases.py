# Copyright 2021 - 2022 Universität Tübingen, DKFZ and EMBL
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

"""Tests edge cases not covered by the typical journey test."""


import pytest
from fastapi import status
from hexkit.providers.mongodb.testutils import mongodb_fixture  # noqa: F401
from hexkit.providers.s3.testutils import file_fixture  # noqa: F401
from hexkit.providers.s3.testutils import s3_fixture  # noqa: F401

from dcs.core.data_repository import DataRepositoryConfig
from tests.fixtures.joint import joint_fixture  # noqa: F401
from tests.fixtures.joint import JointFixture


@pytest.mark.asyncio
async def test_get_health(joint_fixture: JointFixture):  # noqa: F811
    """Test the GET /health endpoint"""

    response = await joint_fixture.rest_client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "OK"}


@pytest.mark.asyncio
async def test_access_non_existing(joint_fixture: JointFixture):  # noqa F811
    """Checks that requesting access to a non-existing DRS object fails with the
    expected exception."""

    # Setup DataRepository:
    config = DataRepositoryConfig(
        outbox_bucket="test-outbox",
        drs_server_uri="http://localhost:1234/",  # a dummy, should not be requested
        retry_access_after=1,
    )
    await joint_fixture.s3.populate_buckets(buckets=[config.outbox_bucket])

    # request access to non existing DRS object:
    response = await joint_fixture.rest_client.get("/objects/my-non-existing-id")
    assert response.status_code == status.HTTP_404_NOT_FOUND
