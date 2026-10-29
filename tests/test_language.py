"""Language selection, presentation and independence from native configuration."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import string
import tempfile
import unittest
from unittest.mock import patch
from maa import preferences, cli, menu, install
from maa.i18n import catalog, t, text, error_text
from maa.output import operation, stage, native_output
from maa.store import Error


class Language(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config')})
        self.env.start()
        self.previous = os.environ.pop('MAA_LANGUAGE', None)

    def tearDown(self):
        if self.previous is not None:
            os.environ['MAA_LANGUAGE'] = self.previous
        self.env.stop()
        self.temp.cleanup()

    def test_catalogs_cover_the_same_keys_and_format_values(self):
        formatter = string.Formatter()
        for collection in ('MESSAGES', 'TEXT'):
            zh, en = getattr(catalog('zh_cn'), collection), getattr(catalog('en_us'), collection)
            self.assertEqual(zh.keys(), en.keys())
            for key in zh:
                with self.subTest(key=key):
                    fields = lambda value: sorted(name for _, name, _, _ in formatter.parse(value) if name is not None)
                    self.assertEqual(fields(zh[key]), fields(en[key]))
        with preferences.using('en_us'):
            self.assertEqual(t('layers_value', loaded=5, total=10, percent=50.), '5/10 layers (50.0%)')

    def test_readonly_default_does_not_create_configuration(self):
        self.assertEqual(preferences.language(), 'zh_cn')
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.run(['language']), 0)
        self.assertEqual(json.loads(output.getvalue()), {'language': 'zh_cn'})
        self.assertFalse(preferences.path().exists())

    def test_persistence_preserves_other_fields_and_private_mode(self):
        preferences.path().parent.mkdir(parents=True)
        preferences.path().write_text('{"other": "kept"}')
        preferences.set_language('en_us')
        self.assertEqual(preferences.load(), {'other': 'kept', 'language': 'en_us'})
        self.assertEqual(preferences.path().stat().st_mode & 0o777, 0o600)
        self.assertEqual(t('back'), 'Back')
        preferences.set_language('zh_cn')
        self.assertEqual(t('back'), '返回')

    def test_existing_install_without_language_prompts_and_updates_reuse(self):
        # The installer boundary consults preferences, not product/model markers.
        with patch('maa.menu.interactive', return_value='en_us') as prompt:
            self.assertEqual(preferences.installation_language(), 'en_us')
            prompt.assert_called_once()
        self.assertFalse(preferences.path().exists())
        preferences.set_language('en_us')
        with patch('maa.menu.interactive', side_effect=AssertionError('Unexpected prompt')):
            self.assertEqual(preferences.installation_language(), 'en_us')
            self.assertEqual(preferences.installation_language('zh_cn'), 'zh_cn')

    def test_cancel_interrupt_and_missing_terminal_stop_before_mutation(self):
        for failure in (menu.Cancelled(), KeyboardInterrupt(), OSError('no tty')):
            with self.subTest(failure=type(failure).__name__), patch('maa.install.prepare_dependencies'), \
                    patch('maa.menu.interactive', side_effect=failure), patch('maa.install._product') as change:
                with self.assertRaises(Error if isinstance(failure, OSError) else type(failure)):
                    install.product(self.root / 'unused.pyz', 'none')
                change.assert_not_called()
                self.assertFalse(preferences.path().exists())
        with patch('maa.menu.interactive', side_effect=OSError('no tty')):
            self.assertEqual(preferences.installation_language('en_us'), 'en_us')

    def test_corrupt_and_invalid_preferences_are_not_overwritten(self):
        preferences.path().parent.mkdir(parents=True)
        for content in ('not JSON', '[]', '{"language":"unknown"}'):
            preferences.path().write_text(content)
            with self.assertRaises(Error):
                preferences.set_language('en_us')
            with self.assertRaises(Error):
                preferences.installation_language('en_us')
            self.assertEqual(preferences.path().read_text(), content)

    def test_language_cli_never_instantiates_model_manager(self):
        paths = [self.root / name for name in ('model.json', 'codex.toml', 'im.json', 'receive.json')]
        for path in paths:
            path.write_bytes(b'unchanged configuration fixture')
        with patch('maa.cli.Manager', side_effect=AssertionError('Backend accessed')), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.run(['language', 'en_us']), 0)
        self.assertEqual(json.loads(output.getvalue()), {'language': 'en_us'})
        for path in paths:
            self.assertEqual(path.read_bytes(), b'unchanged configuration fixture')

    def test_help_and_owned_errors_use_saved_language_keep_identifiers(self):
        for language, heading, phrase in (('en_us', 'usage:', 'model is not registered'), ('zh_cn', '用法：', '模型未登记')):
            preferences.set_language(language)
            help_text = cli.parser().format_help()
            self.assertIn(heading, help_text)
            for name in ('codex-local', '--version', 'language'):
                self.assertIn(name, help_text)
            value = Error('Model is not registered: {v0}', v0='模型原名/key')
            self.assertEqual(str(value), 'Model is not registered: 模型原名/key')
            self.assertIn(phrase, error_text(value).lower())
            self.assertIn('模型原名/key', error_text(value))
        self.assertEqual(error_text(Error('NATIVE_FIXTURE_DIAGNOSTIC\nraw body')), 'NATIVE_FIXTURE_DIAGNOSTIC\nraw body')

    def test_progress_uses_one_locale_and_preserves_native_output(self):
        preferences.set_language('en_us')
        stream = io.StringIO()
        with redirect_stderr(stream):
            with operation('应用配置'):
                # A concurrent language change does not mix one progress row.
                preferences.set_language('zh_cn')
                stage('下载 GGUF：{v0}', v0='模型原名.gguf')
                with native_output() as writer:
                    writer.write('原生_DIAGNOSTIC\n')
        value = stream.getvalue()
        self.assertIn('[Success]', value)
        self.assertIn('Apply configuration', value)
        self.assertIn('Download GGUF: 模型原名.gguf', value)
        self.assertIn('原生_DIAGNOSTIC\n', value)
        self.assertNotIn('[成功]', value)
        self.assertNotIn('\x1b', value)
