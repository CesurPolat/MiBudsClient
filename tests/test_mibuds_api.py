"""API integrity, offline behavior, and retry scheduling without network access."""

from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from controllers.bluetooth.device_catalog import _load_app_catalog, install_catalog
from controllers.bluetooth.rcsp import DeviceIdentity
from controllers.device.catalog_sync import CatalogSync
from ui.components.device_status import DeviceStatusCard
import flet as ft
from PIL import Image
from utils.mibuds_api import CatalogClient, parse_extra_data


def response(body):
    result = io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
    result.headers = Message()
    result.headers['Content-Type'] = 'application/json; charset=utf-8'
    return result


class MiBudsApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.clock = Mock(return_value=1000)
        self.client = CatalogClient(cache_dir=self.directory.name, clock=self.clock, app_version='v0.2.0')
        self.catalog = _load_app_catalog()
        self.body = json.dumps(self.catalog, ensure_ascii=False).encode()
        self.version = 'sha256-' + hashlib.sha256(self.body).hexdigest()
        self.check = {
            'schema_version': 1, 'version': self.version, 'sha256': self.version[7:],
            'catalog_url': '/v1/catalogs/' + self.version + '.json',
            'check_interval_seconds': 21600, 'update_available': True,
        }

    @staticmethod
    def png_response():
        content = io.BytesIO()
        Image.new('RGBA', (2, 2), (255, 255, 255, 255)).save(content, format='PNG')
        result = response(content.getvalue())
        result.headers.replace_header('Content-Type', 'image/png')
        return result

    def test_image_is_downloaded_once_and_reused_offline_after_restart(self):
        with patch('utils.mibuds_api.urlopen', return_value=self.png_response()) as network:
            image_path = self.client.cache_image('/assets/png/earbuds.png')
        self.assertTrue(Path(image_path).is_file())
        self.assertIn('assets', Path(image_path).parts)
        self.assertEqual(network.call_count, 1)
        restarted = CatalogClient(cache_dir=self.directory.name, clock=self.clock)
        with patch('utils.mibuds_api.urlopen', side_effect=AssertionError('Unexpected request')):
            self.assertEqual(restarted.cache_image('/assets/png/earbuds.png'), image_path)

    def test_changed_image_url_downloads_a_separate_file(self):
        with patch('utils.mibuds_api.urlopen', side_effect=[self.png_response(), self.png_response()]) as network:
            first = self.client.cache_image('/assets/png/first.png')
            second = self.client.cache_image('/assets/png/second.png')
        self.assertNotEqual(first, second)
        self.assertEqual(network.call_count, 2)

    def test_last_device_preview_restores_without_network_or_discovery(self):
        with patch('utils.mibuds_api.urlopen', return_value=self.png_response()):
            image_path = self.client.cache_image('/assets/png/earbuds-black.png')
        self.client.remember_device_image('Saved earbuds', image_path)
        restarted = CatalogClient(cache_dir=self.directory.name, clock=self.clock)
        publish = Mock()
        name = Mock(return_value='')
        with patch('utils.mibuds_api.urlopen', side_effect=AssertionError('Unexpected request')):
            sync = CatalogSync(publish=publish, get_identity=lambda: None, get_device_name=name,
                               app_version='v0.2.0', client=restarted)
            self.assertEqual(sync.cached_device, ('Saved earbuds', image_path))
            sync._publish_device()
            sync._publish_device()
        publish.assert_not_called()
        name.return_value = 'Redmi Buds 6'
        sync._publish_device()
        self.assertEqual(' '.join(publish.call_args.args[0]['name'].split()), 'Redmi Buds 6')
        self.assertNotEqual(publish.call_args.args[0]['image_path'], image_path)

    def test_existing_image_cache_is_recovered_without_last_device_record(self):
        with patch('utils.mibuds_api.urlopen', return_value=self.png_response()):
            image_path = self.client.cache_image('/assets/png/earbuds.png')
        with patch('utils.mibuds_api.urlopen', side_effect=AssertionError('Unexpected request')):
            self.assertEqual(self.client.load_last_device_image(), ('', image_path))
        self.assertTrue(Path(self.directory.name, 'last_device.json').is_file())

    def test_missing_or_corrupt_saved_image_does_not_break_startup(self):
        with patch('utils.mibuds_api.urlopen', return_value=self.png_response()):
            image_path = self.client.cache_image('/assets/png/earbuds.png')
        self.client.remember_device_image('Saved earbuds', image_path)
        Path(image_path).write_bytes(b'broken')
        self.assertEqual(self.client.load_last_device_image(), ('', ''))
        Path(image_path).unlink()
        self.assertEqual(self.client.load_last_device_image(), ('', ''))

    def test_corrupt_image_cache_is_repaired(self):
        with patch('utils.mibuds_api.urlopen', return_value=self.png_response()):
            image_path = self.client.cache_image('/assets/png/earbuds.png')
        Path(image_path).write_bytes(b'broken image')
        with patch('utils.mibuds_api.urlopen', return_value=self.png_response()) as network:
            self.assertEqual(self.client.cache_image('/assets/png/earbuds.png'), image_path)
        self.assertEqual(network.call_count, 1)
        with Image.open(image_path) as image:
            image.verify()

    def test_invalid_download_is_not_cached_or_retried_immediately(self):
        with patch('utils.mibuds_api.urlopen', return_value=response({'error': 'not an image'})) as network:
            self.assertEqual(self.client.cache_image('/assets/png/broken.png'), '')
            self.assertEqual(self.client.cache_image('/assets/png/broken.png'), '')
        self.assertEqual(network.call_count, 1)
        self.assertEqual(list(Path(self.directory.name).rglob('*.png')), [])

    def test_image_rate_limit_respects_retry_after_across_urls(self):
        error = HTTPError(self.client.base_url, 429, 'limited', {'Retry-After': '120'}, io.BytesIO())
        with patch('utils.mibuds_api.urlopen', side_effect=error) as network:
            self.assertEqual(self.client.cache_image('/assets/png/first.png'), '')
            self.assertEqual(self.client.cache_image('/assets/png/second.png'), '')
        self.assertEqual(network.call_count, 1)
        self.assertEqual(self.client.next_image_retry_at, 1120)
        self.clock.return_value = 1120
        with patch('utils.mibuds_api.urlopen', return_value=self.png_response()):
            self.assertTrue(self.client.cache_image('/assets/png/second.png'))

    def populate(self):
        with patch('utils.mibuds_api.urlopen', side_effect=[response(self.check), response(self.body)]) as request:
            self.assertTrue(self.client.refresh(0x2717, 0x509b))
        return request

    def test_verified_snapshot_persists_and_restart_avoids_download(self):
        request = self.populate()
        first = request.call_args_list[0].args[0]
        query = parse_qs(urlsplit(first.full_url).query)
        self.assertEqual(query, {'vid': ['2717'], 'pid': ['509b']})
        self.assertEqual(first.get_header('X-mibuds-app-version'), '0.2.0')
        self.assertEqual(first.get_header('X-mibuds-install-id'), self.client.install_id)
        self.assertIsNone(request.call_args_list[1].args[0].get_header('X-mibuds-install-id'))
        self.assertTrue(request.call_args_list[1].args[0].full_url.endswith(self.check['catalog_url']))
        restarted = CatalogClient(cache_dir=self.directory.name, clock=self.clock)
        self.assertEqual(restarted.catalog, self.catalog)
        self.assertEqual(restarted.install_id, self.client.install_id)
        with patch('utils.mibuds_api.urlopen') as network:
            self.assertFalse(restarted.refresh())
        network.assert_not_called()

    def test_install_id_is_random_uuid4_and_survives_catalog_deletion(self):
        install_id = self.client.install_id
        self.assertEqual(UUID(install_id).version, 4)
        self.assertEqual(self.client.install_id_file.read_text(encoding='ascii'), install_id)
        self.populate()
        self.client.cache_file.unlink()
        restarted = CatalogClient(cache_dir=self.directory.name, clock=self.clock)
        self.assertEqual(restarted.install_id, install_id)
        self.assertIsNone(restarted.catalog)

    def test_invalid_saved_install_id_is_replaced_with_valid_uuid4(self):
        self.client.install_id_file.write_text('invalid', encoding='ascii')
        restarted = CatalogClient(cache_dir=self.directory.name)
        self.assertEqual(UUID(restarted.install_id).version, 4)
        self.assertNotEqual(restarted.install_id, self.client.install_id)
        self.assertEqual(restarted.install_id_file.read_text(encoding='ascii'), restarted.install_id)

    def test_install_id_storage_failure_does_not_break_catalog_requests(self):
        self.client.install_id_file.unlink()
        with patch('utils.mibuds_api.Path.write_text', side_effect=PermissionError('read-only')):
            client = CatalogClient(cache_dir=self.directory.name, clock=self.clock)
        self.assertIsNone(client.install_id)
        with patch('utils.mibuds_api.urlopen', side_effect=[response(self.check), response(self.body)]) as request:
            self.assertTrue(client.refresh())
        self.assertIsNone(request.call_args_list[0].args[0].get_header('X-mibuds-install-id'))

    def test_due_check_sends_version_and_reuses_unchanged_snapshot(self):
        self.populate()
        self.clock.return_value = 23000
        self.check['update_available'] = False
        with patch('utils.mibuds_api.urlopen', return_value=response(self.check)) as network:
            self.assertFalse(self.client.refresh())
        self.assertEqual(network.call_count, 1)
        self.assertEqual(parse_qs(urlsplit(network.call_args.args[0].full_url).query)['version'], [self.version])

    def test_corrupt_download_cannot_replace_last_good_cache(self):
        self.populate()
        self.clock.return_value = 23000
        self.check['version'] = 'sha256-' + 'a' * 64
        self.check['sha256'] = 'a' * 64
        with patch('utils.mibuds_api.urlopen', side_effect=[response(self.check), response(b'{}')]):
            self.assertFalse(self.client.refresh())
        self.assertEqual(self.client.catalog, self.catalog)
        self.assertEqual(self.client.version, self.version)
        self.assertIn('SHA-256', self.client.last_error)
        self.assertEqual(CatalogClient(cache_dir=self.directory.name).catalog, self.catalog)

    def test_rate_limit_honors_retry_after_and_exponential_backoff(self):
        def limited(request, timeout):
            raise HTTPError(request.full_url, 429, 'limited', {'Retry-After': '120'}, io.BytesIO())
        with patch('utils.mibuds_api.urlopen', side_effect=limited) as network:
            self.assertFalse(self.client.refresh())
            self.assertEqual(self.client.next_check_at, 1120)
            self.client.refresh()
            self.assertEqual(network.call_count, 1)
            self.clock.return_value = 1120
            self.client.refresh()
            self.assertEqual(self.client.next_check_at, 1240)
            self.clock.return_value = 1240
            self.client.refresh()
            self.assertEqual(self.client.next_check_at, 1480)

    def test_client_errors_are_not_automatically_retried(self):
        for status in (400, 404, 405):
            with self.subTest(status=status):
                client = CatalogClient(cache_dir=self.directory.name, clock=self.clock)
                error = HTTPError(self.client.base_url, status, 'bad request', {}, io.BytesIO())
                with patch('utils.mibuds_api.urlopen', side_effect=error) as network:
                    client.refresh()
                    self.clock.return_value += 100000
                    client.refresh()
                self.assertEqual(network.call_count, 1)

    def test_offline_start_preserves_bundled_catalog_and_corrupt_cache_is_ignored(self):
        with patch('utils.mibuds_api.urlopen', side_effect=URLError('offline')):
            self.assertFalse(self.client.refresh())
        self.assertIsNone(self.client.catalog)
        Path(self.directory.name, 'catalog.json').write_text('{broken', encoding='utf-8')
        client = CatalogClient(cache_dir=self.directory.name)
        self.assertIsNone(client.catalog)
        sync = CatalogSync(publish=Mock(), get_identity=lambda: None, app_version='v0.2.0', client=client,
                           get_device_name=lambda: 'Redmi Buds 6')
        sync._publish_device()
        self.assertEqual(' '.join(sync._publish.call_args.args[0]['name'].split()), 'Redmi Buds 6')

    def test_asset_urls_and_extra_data_are_resolved_without_changing_raw_metadata(self):
        self.assertEqual(self.client.resolve_asset_url('/assets/png/example.png'), self.client.base_url + 'assets/png/example.png')
        for path in ('file:///secret', '//other.example/image.png', 'https://other.example/x'):
            with self.assertRaises(ValueError):
                self.client.resolve_asset_url(path)
        self.assertEqual(parse_extra_data('{"click_action":[0,6]}'), {'click_action': [0, 6]})
        for value in ('invalid', '[]', None):
            self.assertEqual(parse_extra_data(value), {})

    def test_catalog_refresh_updates_existing_identity_and_keeps_image_fallback(self):
        identity = DeviceIdentity(0x2717, 0x509b)
        self.addCleanup(install_catalog, _load_app_catalog())
        for model in self.catalog['result']['tw_product_list']:
            if model['vid'].lower() == '2717' and model['pid'].lower() == '509b':
                model['name'] = 'Updated catalog name'
                model['icon_static'] = [{'color': 1, 'icon_url': '/assets/png/device.png'}]
        install_catalog(self.catalog)
        self.assertEqual(identity.model_name, 'Updated catalog name')
        publish = Mock()
        sync = CatalogSync(publish=publish, get_identity=lambda: identity, app_version='v0.2.0', client=self.client)
        image_path = str(Path(self.directory.name, 'device.png'))
        with patch.object(self.client, 'cache_image', return_value=image_path):
            sync._publish_device()
        message = publish.call_args.args[0]
        self.assertEqual(message['name'], 'Updated catalog name')
        card = DeviceStatusCard()
        card.update_catalog_device(message['name'], message['image_path'])
        self.assertEqual(card.device_image._image_control.src, message['image_path'])
        self.assertIsInstance(card.device_image._image_control.error_content, ft.Icon)
        card.update_catalog_device('Another model')
        self.assertEqual(card.device_image._image_control.src, '')
        self.assertIsInstance(card.device_image.content.content, ft.Icon)

    def test_discovered_model_prefers_black_then_catalog_default_color(self):
        catalog = {'code': 0, 'result': {'tw_product_list': [
            {'vid': '2717', 'pid': '0001', 'name': 'Model A', 'model': 'a',
             'extra_info': {'default_color': 1}, 'icon_static': [
                 {'color': 1, 'icon_url': '/assets/png/a-white.png'},
                 {'color': 3, 'icon_url': '/assets/png/a-black.png'},
             ]},
            {'vid': '2717', 'pid': '0002', 'name': 'Model B', 'model': 'b',
             'extra_info': {'default_color': 3}, 'icon_static': [
                 {'color': 1, 'icon_url': '/assets/png/b-white.png'},
                 {'color': 3, 'icon_url': '/assets/png/b-blue.png'},
             ]},
        ]}}
        self.addCleanup(install_catalog, _load_app_catalog())
        install_catalog(catalog)
        name = Mock(return_value='Model A')
        publish = Mock()
        sync = CatalogSync(publish=publish, get_identity=lambda: None, get_device_name=name,
                           app_version='v0.2.0', client=self.client)
        with patch.object(self.client, 'cache_image', side_effect=lambda url: str(Path(self.directory.name, url.rsplit('/', 1)[-1]))) as cache:
            sync._publish_device()
            self.assertTrue(publish.call_args.args[0]['image_path'].endswith('a-black.png'))
            self.assertTrue(cache.call_args.args[0].endswith('/a-black.png'))
            name.return_value = 'Model B'
            sync._publish_device()
            self.assertTrue(publish.call_args.args[0]['image_path'].endswith('b-blue.png'))
            name.return_value = ''
            sync._publish_device()
            self.assertEqual(publish.call_args.args[0]['image_path'], '')


if __name__ == '__main__':
    unittest.main()
