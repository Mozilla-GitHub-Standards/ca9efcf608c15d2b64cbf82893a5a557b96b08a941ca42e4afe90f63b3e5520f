# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from requests import exceptions


class HTTPError(exceptions.HTTPError):
    """An HTTP error occurred.

    Provides two arguments. First the response status code and second the
    full response object.
    """