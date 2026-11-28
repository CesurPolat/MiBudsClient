"""Error reports with consent dialogs, automatic Bluetooth reports and durable delivery."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import threading
import time
import traceback
import functools
import inspect
from contextlib import nullcontext
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from uuid import uuid4

from ..api.mibuds_api import DeliveryError, ErrorReportClient, encode_report
from utils.app.pubsub_topics import PubSubTopic


@functools.lru_cache(maxsize=1)
def implementation_diagnostics():
    """Identify the Bluetooth implementation using the available source files."""
    from ui.constants import APP_VERSION

    directory = Path(__file__).resolve().parents[2] / 'controllers' / 'bluetooth'
    fingerprint = None
    try:
        if (directory / 'controller.py').is_file():
            digest = hashlib.sha256()
            for path in sorted(directory.rglob('*.py')):
                digest.update(path.relative_to(directory).as_posix().encode('utf-8'))
                digest.update(path.read_bytes())
            fingerprint = digest.hexdigest()
    except OSError:
        pass
    return {'app_version': APP_VERSION, 'bluetooth_source_sha256': fingerprint}


def redact(value):
    text = str(value)
    for root in {str(Path.home()), os.environ.get('USERPROFILE', ''), os.environ.get('HOME', '')}:
        if root:
            text = re.sub(re.escape(root), '[user]', text, flags=re.I)
    text = re.sub(r'(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b', '[address]', text)
    text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[address]', text)
    text = re.sub(r'(?i)\b(?:https?://|www\.)\S+', '[url]', text)
    text = re.sub(r'(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b', '[email]', text)
    text = re.sub(r'(?i)(\b(?:password|passwd|token|secret|api[_-]?key|authorization)\b[\s\"\x27:=]+)(?:Bearer\s+)?[^\s,;\"\x27}]+', r'\1[redacted]', text)
    text = re.sub(r'(?i)\bBearer\s+\S+', 'Bearer [redacted]', text)
    text = re.sub(r'(?i)[a-z]:[\\/]users[\\/][^\\/\s]+|/home/[^/\s]+', '[user]', text)
    return text


def make_report(error, *, app_version='', device='', action='', tb=None, identity=None):
    frames = traceback.extract_tb(tb if tb is not None else error.__traceback__)
    stack = '\n'.join(f'{Path(frame.filename).name}:{frame.lineno} in {frame.name}' for frame in frames)
    # Preserve handled transport causes and safe metadata within the existing
    # API schema. Never collect socket data, auth challenges, or frame locals.
    causes, current, visited = [], error, set()
    while current is not None and id(current) not in visited and len(causes) < 8:
        visited.add(id(current))
        causes.append(f'{type(current).__name__}: {str(current)[:256]} '
                      f'(errno={getattr(current, "errno", None)}, winerror={getattr(current, "winerror", None)})')
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    diagnostics = getattr(error, 'bluetooth_diagnostics', None)
    if diagnostics is not None:
        if 'implementation' not in diagnostics:
            diagnostics = {**diagnostics, 'implementation': implementation_diagnostics()}
        stack += '\n\nBluetooth diagnostics:\n' + json.dumps(diagnostics, ensure_ascii=False, default=str)
        stack += '\nCauses:\n' + '\n'.join(causes)
    if identity is not None and diagnostics is None:
        stack += '\n\nDevice identity:\n' + json.dumps(identity, ensure_ascii=False, default=str)
    report = {
        'message': redact(str(error) or type(error).__name__)[:4096],
        'name': type(error).__name__[:128], 'stack': redact(stack)[-16000:],
        'app_version': app_version.lstrip('v')[:64],
        'os': f'{platform.system()} {platform.release()}'[:256],
        'device': redact(device)[:512],
        'occurred_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'details': {'action': redact(action)[:128], 'description': ''},
    }
    # Leave space for 4000 characters of user description, including 4-byte Unicode.
    while len(json.dumps(report, ensure_ascii=False).encode('utf-8')) > 48000 and report['stack']:
        report['stack'] = report['stack'][1000:]
    return report


def publish_exception(publish, error, action):
    """Report caught programming errors without changing existing result callbacks."""
    if isinstance(error, (OSError, TimeoutError)):
        return
    try:
        publish(PubSubTopic.REPORT_EXCEPTION, error=error, action=action)
    except Exception:
        pass


def guard_ui_callbacks(root, capture, *, ui_lock=None):
    """Catch Python handler failures before Flet consumes their exceptions."""
    visited = set()
    def visit(value):
        if id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
        elif is_dataclass(value) and not isinstance(value, type):
            for field in fields(value):
                if field.name.startswith('_') or field.name in {'parent', 'data'}:
                    continue
                handler = getattr(value, field.name, None)
                if field.name.startswith('on_') and callable(handler):
                    def wrap(callback, action):
                        if inspect.iscoroutinefunction(callback):
                            @functools.wraps(callback)
                            async def guarded(*args, **kwargs):
                                try:
                                    return await callback(*args, **kwargs)
                                except Exception as exc:
                                    capture(exc, action)
                        else:
                            @functools.wraps(callback)
                            def guarded(*args, **kwargs):
                                with ui_lock if ui_lock is not None else nullcontext():
                                    try:
                                        return callback(*args, **kwargs)
                                    except Exception as exc:
                                        capture(exc, action)
                        return guarded
                    setattr(value, field.name, wrap(handler, f'{type(value).__name__}.{field.name}'))
                else:
                    visit(handler)
    visit(root)


def queue_directory():
    if sys.platform == 'win32':
        root = Path(os.getenv('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    else:
        root = Path(os.getenv('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return root / 'MiBudsClient' / 'error_reports'


class ReportQueue:
    delays = (60, 300, 1800, 7200)

    def __init__(self, *, directory=None, client=None, clock=time.time, notify=lambda *args: None,
                 on_report_status=None):
        self.directory = Path(directory) if directory is not None else queue_directory()
        self.client, self.clock, self.notify = client or ErrorReportClient(), clock, notify
        self.lock = threading.RLock()
        self.wake, self.stopped = threading.Event(), threading.Event()
        self.worker = None
        self.on_report_status = on_report_status

    def _report_status(self, report, state):
        print(redact(f"[Error reports] state={state} "
                     f"action={report.get('details', {}).get('action', '')} "
                     f"occurred_at={report.get('occurred_at', '')}"))
        if self.on_report_status is not None:
            try:
                self.on_report_status({
                    'state': state, 'action': report.get('details', {}).get('action', ''),
                    'occurred_at': report.get('occurred_at', ''),
                })
            except Exception:
                pass  # UI feedback must not interrupt durable report delivery.

    def _records(self):
        records = []
        for path in self.directory.glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                if (self.clock() - record['created'] >= 7 * 86400
                        or (record['attempts'] >= 5 and record['next'] <= self.clock())):
                    path.unlink()
                    self._report_status(record['report'], 'failed')
                else:
                    encode_report(record['report'])
                    records.append((path, record))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return records

    def _save(self, path, record):
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)

    def enqueue(self, report):
        """Persist authorized manual or automatic reports before attempting HTTP."""
        encode_report(report)
        with self.lock:
            if len(self._records()) >= 20:
                self._report_status(report, 'failed')
                return False
            try:
                self._save(self.directory / f'{uuid4()}.json', {
                    'created': self.clock(), 'attempts': 0, 'next': self.clock(), 'report': report,
                })
            except OSError:
                self._report_status(report, 'failed')
                return False
            self._report_status(report, 'queued')
        self.wake.set()
        return True

    def process_due(self):
        with self.lock:
            records = self._records()
        for path, record in records:
            if record['next'] > self.clock() or self.stopped.is_set():
                continue
            # Persist the attempt before network I/O so restarts cannot reset the limit.
            record['attempts'] += 1
            record['next'] = self.clock() + self.delays[min(record['attempts'] - 1, 3)]
            self._save(path, record)
            try:
                self.client.send(record['report'])
            except DeliveryError as exc:
                if not exc.retryable or record['attempts'] >= 5:
                    path.unlink()
                    self._report_status(record['report'], 'failed')
                    self.notify('failed')
                else:
                    record['next'] = max(record['next'], self.clock() + exc.delay)
                    self._save(path, record)
                    self._report_status(record['report'], 'queued')
                    self.notify('queued')
            else:
                path.unlink()
                self._report_status(record['report'], 'sent')
                self.notify('sent')

    def start(self):
        if self.worker is not None:
            return
        def run():
            while not self.stopped.is_set():
                self.wake.clear()
                try:
                    self.process_due()
                except Exception:
                    # Queue/transport failures must never enter the exception reporter.
                    try:
                        self.notify('failed')
                    except Exception:
                        pass
                self.wake.wait(1)
        self.worker = threading.Thread(target=run, daemon=True, name='error-report-delivery')
        self.worker.start()

    def stop(self):
        self.stopped.set()
        self.wake.set()


class ErrorReportManager:
    AUTOMATIC_ACTIONS = frozenset({'bluetooth_connect', 'bluetooth_discovery', 'bluetooth_receive'})

    def __init__(self, *, publish, app_version, get_device, auto_submit=None, get_identity=None):
        self.publish, self.app_version, self.get_device = publish, app_version, get_device
        self.auto_submit = auto_submit
        self.get_identity = get_identity
        self.seen = set()
        self.lock = threading.Lock()

    def capture(self, error, action='', tb=None):
        signature = None
        try:
            report = make_report(error, app_version=self.app_version,
                                 device=self.get_device(), action=action, tb=tb,
                                 identity=self.get_identity() if self.get_identity is not None else None)
            signature = hashlib.sha256(encode_report({key: report[key] for key in ('name', 'message', 'stack')})).hexdigest()
            with self.lock:
                if signature in self.seen:
                    print(redact(f'[Error reports] Duplicate report skipped: action={action}'))
                    return
                self.seen.add(signature)
            if action in self.AUTOMATIC_ACTIONS and self.auto_submit is not None:
                if not self.auto_submit(report):
                    with self.lock:
                        self.seen.discard(signature)
                    print('[Error reports] Could not queue automatic Bluetooth report.')
                    self.publish(PubSubTopic.ERROR_REPORT_STATUS, state='failed')
                return
            self.publish(PubSubTopic.ERROR_REPORT, report=report)
        except Exception as exc:
            print(f'[Error reports] Could not prepare report: {redact(exc)}')
            if signature is not None:
                with self.lock:
                    self.seen.discard(signature)
