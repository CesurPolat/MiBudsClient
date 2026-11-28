"""Encode and deliver diagnostic reports to the MiBuds API."""

import json
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from .http import API_BASE_URL, retry_after


def encode_report(report):
    body = json.dumps(report, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(body) > 65536:
        raise ValueError('Report exceeds UTF-8 body limit')
    return body


class DeliveryError(Exception):
    def __init__(self, retryable, delay=0):
        self.retryable, self.delay = retryable, delay


class ErrorReportClient:
    def __init__(self, base_url=API_BASE_URL, transport=urlopen, clock=time.time):
        self.url = base_url.rstrip('/') + '/v1/errors'
        self.transport, self.clock = transport, clock

    def send(self, report):
        request = Request(self.url, data=encode_report(report), method='POST', headers={
            'Content-Type': 'application/json', 'Accept': 'application/json',
            'X-MiBuds-App-Version': report.get('app_version', ''),
            'User-Agent': f"MiBudsClient/{report.get('app_version') or 'dev'}",
        })
        try:
            with self.transport(request, timeout=10) as response:
                if response.status != 201:
                    raise DeliveryError(response.status == 429 or response.status >= 500)
                result = json.loads(response.read(8193))
                UUID(result['id'])
                stamp = datetime.fromisoformat(result['received_at'].replace('Z', '+00:00'))
                if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                    raise ValueError('Expected UTC timestamp')
        except HTTPError as exc:
            value = exc.headers.get('Retry-After') if exc.headers else None
            delay = retry_after(value, self.clock, default=0)
            exc.close()
            raise DeliveryError(exc.code == 429 or exc.code >= 500, delay) from None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise DeliveryError(True) from None
