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

"""Interfaces for object storage adapters and the exception they may throw."""

from abc import ABC, abstractmethod


class DrsEventBroadcasterPort(ABC):
    """A port through which DRS-specific events are communicated with the outside."""

    @abstractmethod
    def download_served(self, *, file_id: str) -> None:
        """Communicate the event of an download being served. This can be relevant for
        auditing purposes."""
        ...

    @abstractmethod
    def unstaged_download_requested(self, *, file_id: str) -> None:
        """Communicates the event that a download was requested for a DRS object, that
        is not jet available in the outbox."""
        ...

    @abstractmethod
    def new_file_registered(
        self, *, drs_id: str, drs_self_uri: str, file_id: str
    ) -> None:
        """Communicates the event that a file has been registered."""
        ...
