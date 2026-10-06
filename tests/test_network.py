"""Verify per-sync proxy routing and TLS isolation."""
import ssl
import unittest
from unittest.mock import patch
from urllib.request import HTTPSHandler, ProxyHandler

from star_savior.network import sync_opener, validate_proxy
from star_savior.website import FILES, download


class NetworkTests(unittest.TestCase):
    def test_invalid_proxy_is_rejected(self):
        for value in ('socks5://localhost:1080', 'localhost:7890',
                      'http://user:password@localhost:7890',
                      'http://localhost:0', 'http://localhost:99999',
                      'http://localhost:7890/path'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_proxy(value)
        self.assertEqual(validate_proxy('  http://127.0.0.1:7890  '),
                         'http://127.0.0.1:7890')

    def test_proxy_and_tls_are_local_to_opener(self):
        secure = sync_opener('http://127.0.0.1:7890')
        proxy = next(h for h in secure.handlers if isinstance(h, ProxyHandler))
        self.assertEqual(proxy.proxies['https'], 'http://127.0.0.1:7890')
        tls = next(h for h in secure.handlers if isinstance(h, HTTPSHandler))._context
        self.assertEqual(tls.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(tls.check_hostname)
        insecure = sync_opener(verify_tls=False)
        tls = next(h for h in insecure.handlers if isinstance(h, HTTPSHandler))._context
        self.assertEqual(tls.verify_mode, ssl.CERT_NONE)
        self.assertFalse(tls.check_hostname)
        self.assertEqual(ssl.create_default_context().verify_mode, ssl.CERT_REQUIRED)

    def test_all_resources_use_configured_opener(self):
        with patch('star_savior.website.sync_opener') as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b'{}'
            factory.return_value.open.side_effect = lambda request, **kwargs: self.response(request)
            result = download('http://127.0.0.1:7890', False)
            factory.assert_called_once_with('http://127.0.0.1:7890', False)
            self.assertEqual(set(result), set(FILES))
            self.assertEqual(factory.return_value.open.call_count, len(FILES))

    @staticmethod
    def response(request):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.url = request.full_url
        response.read.return_value = b'{}'
        return response
