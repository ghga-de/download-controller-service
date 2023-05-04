# Copyright 2023 Universität Tübingen, DKFZ, EMBL, and Universität zu Köln
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
"""TODO"""

__all__ = ["require_work_order_token"]

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


async def require_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=True)),
) -> str:
    """Require an access token using FastAPI."""
    return credentials.credentials


require_work_order_token = Security(require_access_token)