# Copyright 2021 - 2023 Universität Tübingen, DKFZ, EMBL, and Universität zu Köln
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

"""Main business-logic of this service"""

import hashlib
import os
import re
from datetime import datetime, timedelta

import requests
from pydantic import BaseSettings, Field, validator

from dcs.adapters.outbound.http import exceptions
from dcs.adapters.outbound.http.api_calls import call_ekss_api
from dcs.core import models
from dcs.ports.inbound.data_repository import DataRepositoryPort
from dcs.ports.outbound.dao import (
    DownloadDaoPort,
    DrsObjectDaoPort,
    EnvelopeDaoPort,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
)
from dcs.ports.outbound.event_pub import EventPublisherPort
from dcs.ports.outbound.storage import ObjectStoragePort


class DataRepositoryConfig(BaseSettings):
    """Config parameters needed for the DataRepository."""

    outbox_bucket: str
    drs_server_uri: str = Field(
        ...,
        description="The base of the DRS URI to access DRS objects. Has to start with 'drs://'"
        + " and end with '/'.",
        example="drs://localhost:8080/",
    )
    retry_access_after: int = Field(
        120,
        description="When trying to access a DRS object that is not yet in the outbox, instruct"
        + " to retry after this many seconds.",
    )
    ekss_base_url: str = Field(
        ...,
        description="URL containing host and port of the EKSS endpoint to retrieve"
        + " personalized envelope from",
        example="http://ekss:8080/",
    )

    # pylint: disable=no-self-argument
    @validator("drs_server_uri")
    def check_server_uri(cls, value: str):
        """Checks the drs_server_uri."""

        if not re.match(r"^drs://.+/$", value):
            raise ValueError(
                f"The drs_server_uri has to start with 'drs://' and end with '/', got : {value}"
            )

        return value


class DataRepository(DataRepositoryPort):
    """A service that manages a registry of DRS objects."""

    def __init__(
        self,
        *,
        config: DataRepositoryConfig,
        download_dao: DownloadDaoPort,
        drs_object_dao: DrsObjectDaoPort,
        envelope_dao: EnvelopeDaoPort,
        object_storage: ObjectStoragePort,
        event_publisher: EventPublisherPort,
    ):
        """Initialize with essential config params and outbound adapters."""

        self._config = config
        self._event_publisher = event_publisher
        self._download_dao = download_dao
        self._drs_object_dao = drs_object_dao
        self._envelope_dao = envelope_dao
        self._object_storage = object_storage

    async def _check_envelope(
        self, *, secret_id: str, envelope_id: str, public_key: str, api_base: str
    ):
        """Checks if an DB entry exists for the envelope id and creates one, if not"""
        try:
            await self._envelope_dao.get_by_id(id_=envelope_id)
        except ResourceNotFoundError:
            try:
                envelope_header = call_ekss_api(
                    secret_id=secret_id,
                    receiver_public_key=public_key,
                    api_base=api_base,
                )
            except exceptions.BadResponseCodeError as error:
                raise self.UnexpectedAPIResponseError(
                    api_url=api_base, response_code=error.response_code
                ) from error
            except exceptions.RequestFailedError as error:
                raise self.APICommunicationError(api_url=api_base) from error
            except exceptions.SecretNotFoundError as error:
                raise self.SecretNotFoundError(message=str(error)) from error

            envelope = models.Envelope(
                id=envelope_id,
                header=envelope_header,
                offset=len(envelope_header),
                creation_timestamp=datetime.utcnow().isoformat(),
            )
            # no need for duplicate id check, branch only triggered if this does not exist
            await self._envelope_dao.insert(dto=envelope)

    async def _generate_download_uri(self, *, file_id: str, envelope_id: str):
        """Generates a download_id, signature and creates a corresponding DB entry"""
        download_id = os.urandom(32).hex()
        signature = os.urandom(32).hex()

        expiration_datetime = datetime.utcnow() + timedelta(seconds=30)

        download = models.Download(
            id=download_id,
            file_id=file_id,
            envelope_id=envelope_id,
            signature_hash=hashlib.sha256(signature).hexdigest(),  # type: ignore[arg-type]
            expiration_datetime=expiration_datetime.isoformat(),
        )
        try:
            await self._download_dao.insert(dto=download)
        except ResourceAlreadyExistsError as error:
            raise self.DuplicateEntryError(
                db_name="downloads", previous_message=str(error)
            ) from error

        host = self._config.drs_server_uri.replace("drs://", "http://")
        return f"{host}downloads/{download_id}/?signature={signature}"

    def _get_drs_uri(self, *, drs_id: str) -> str:
        """Construct DRS URI for the given DRS ID."""

        return f"{self._config.drs_server_uri}{drs_id}"

    def _get_model_with_self_uri(
        self, *, drs_object: models.DrsObject
    ) -> models.DrsObjectWithUri:
        """Add the DRS self URI to an DRS object."""

        return models.DrsObjectWithUri(
            **drs_object.dict(),
            self_uri=self._get_drs_uri(drs_id=drs_object.id),
        )

    async def _get_access_model(
        self, *, drs_object: models.DrsObject, access_url: str
    ) -> models.DrsObjectWithAccess:
        """Get a DRS Object model with access information."""

        return models.DrsObjectWithAccess(
            **drs_object.dict(),
            self_uri=self._get_drs_uri(drs_id=drs_object.id),
            access_url=access_url,
        )

    async def access_drs_object(
        self, *, drs_id: str, public_key: str
    ) -> models.DrsObjectWithAccess:
        """
        Serve the specified DRS object with access information.
        If it does not exists in the outbox, yet, a RetryAccessLaterError is raised that
        instructs to retry the call after a specified amount of time.
        """

        # make sure that metadata for the DRS object exists in the database:
        try:
            drs_object = await self._drs_object_dao.get_by_id(drs_id)
        except ResourceNotFoundError as error:
            raise self.DrsObjectNotFoundError(drs_id=drs_id) from error

        drs_object_with_uri = self._get_model_with_self_uri(drs_object=drs_object)

        # check if the file corresponding to the DRS object is already in the outbox:
        if not await self._object_storage.does_object_exist(
            bucket_id=self._config.outbox_bucket, object_id=drs_object.file_id
        ):
            # publish an event to request a stage of the corresponding file:
            await self._event_publisher.unstaged_download_requested(
                drs_object=drs_object_with_uri
            )

            # instruct to retry later:
            raise self.RetryAccessLaterError(
                retry_after=self._config.retry_access_after
            )

        file_id = drs_object.file_id
        envelope_id = hashlib.sha256(file_id + public_key).hexdigest()

        await self._check_envelope(
            secret_id=drs_object_with_uri.decryption_secret_id,
            envelope_id=envelope_id,
            public_key=public_key,
            api_base=self._config.ekss_base_url,
        )

        download_uri = await self._generate_download_uri(
            file_id=file_id, envelope_id=envelope_id
        )

        drs_object_with_access = await self._get_access_model(
            drs_object=drs_object, access_url=download_uri
        )

        # publish an event indicating the served download:
        await self._event_publisher.download_served(drs_object=drs_object_with_uri)

        return drs_object_with_access

    async def register_new_file(self, *, file: models.FileToRegister):
        """Register a file as a new DRS Object."""

        # write file entry to database
        drs_object = await self._drs_object_dao.insert(file)

        # publish message that the drs file has been registered
        drs_object_with_uri = self._get_model_with_self_uri(drs_object=drs_object)
        await self._event_publisher.file_registered(drs_object=drs_object_with_uri)

    async def validate_download_information(
        self, *, download_id: str, signature: str
    ) -> tuple[models.Envelope, str]:
        """
        Checks if the request download exists and the link is not yet expired, then
        retrieves envelope data.

        :returns: IDs of the envelope and file_id corresponding to the requested download
        """

        try:
            current_part_download = await self._download_dao.get_by_id(download_id)
        except ResourceNotFoundError as error:
            raise self.DownloadNotFoundError() from error

        signature_hash = hashlib.sha256(signature)  # type: ignore[arg-type]
        if not current_part_download.signature_hash == signature_hash:
            raise self.DownloadNotFoundError()

        expiration_datetime = datetime.fromisoformat(
            current_part_download.expiration_datetime
        )
        now = datetime.utcnow()
        duration = expiration_datetime - now

        if duration.total_seconds() <= 0:
            raise self.DonwloadLinkExpired()

        try:
            envelope_data = await self._envelope_dao.get_by_id(
                current_part_download.envelope_id
            )
        except ResourceNotFoundError as error:
            raise self.EnvelopeNotFoundError(download_id=download_id) from error

        return envelope_data, current_part_download.file_id

    async def serve_redirect(
        self, *, object_id: str, parsed_range: tuple[int, int]
    ) -> tuple[str, dict[str, str]]:
        """
        TODO

        :returns: a tuple containing an S3 URL with adjusted range corresponding to envelope offset
        """

        redirect_url = await self._object_storage.get_object_download_url(
            bucket_id=self._config.outbox_bucket, object_id=object_id
        )

        return redirect_url, {
            "Redirect-Range": f"bytes={parsed_range[0]-parsed_range[1]}"
        }

    async def serve_envelope_part(
        self, *, object_id: str, parsed_range: tuple[int, int], envelope_header: bytes
    ) -> bytes:
        """
        TODO

        :returns: bytes containing both the envelope and the first file part
        """
        range_header = {"Range": f"bytes={parsed_range[0]-parsed_range[1]}"}
        redirect_url = await self._object_storage.get_object_download_url(
            bucket_id=self._config.outbox_bucket, object_id=object_id
        )
        try:
            response = requests.get(url=redirect_url, headers=range_header, timeout=60)
        except requests.ConnectionError as error:
            raise self.APICommunicationError(api_url=redirect_url) from error
        return envelope_header + response.content
