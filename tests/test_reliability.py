"""First-use, Windows I/O, render recovery and Agent/browser handoff regressions."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import bootstrap_runtime as bootstrap
import local_io
import render
import resume_model
import serve
import session


def fixture(template='rendercv-harvard', language='en'):
    return {'schema_version': 1, 'meta': {'purpose': 'job', 'target_position': 'Test Role',
      'language_mode': language, 'page_target': 1, 'template_id': template},
      'basics': {'name': 'Test Candidate', 'headline': 'Fictional audit data', 'contacts': []},
      'sections': [{'id': 'education', 'type': 'education', 'title': 'Education',
        'entries': [{'id': 'entry-1', 'title': 'Example University', 'subtitle': 'Computer Science',
          'date': '2020 - 2024', 'location': '', 'bullets': [{'id': 'bullet-1', 'text': 'Test content.'}]}]}]}


class IOTests(unittest.TestCase):
    def test_powershell_utf8_bom_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'resume.json'
            path.write_text(json.dumps(fixture()), encoding='utf-8-sig')
            self.assertEqual(resume_model.load_resume(path), fixture())

    def test_powershell_out_file_utf16_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'resume.json'
            path.write_text(json.dumps(fixture()), encoding='utf-16')
            self.assertEqual(resume_model.load_resume(path), fixture())

    def test_short_windows_file_lock_is_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'resume.json'
            original = os.replace
            calls = []
            def occupied(source, target):
                calls.append(1)
                if len(calls) < 3:
                    raise PermissionError('sharing violation')
                return original(source, target)
            with patch.object(local_io.os, 'replace', side_effect=occupied):
                resume_model.save_resume(path, fixture())
            self.assertEqual(len(calls), 3)
            self.assertEqual(resume_model.load_resume(path), fixture())

    def test_new_waiter_receives_fast_click_and_does_not_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            session.append_event(tmp, 'template_selected', {'template_id': 'first'})
            session.append_event(tmp, 'template_change_requested', {'template_id': 'second'})
            event = session.wait_for_event(tmp, session.AGENT_EVENTS, timeout=.1)
            self.assertEqual(event['data']['template_id'], 'second')
            self.assertIsNone(session.wait_for_event(tmp, session.AGENT_EVENTS, timeout=.05, poll=.01))
            replay = session.wait_for_event(tmp, session.AGENT_EVENTS, timeout=.1, replay=True)
            self.assertEqual(replay['seq'], event['seq'])

    def test_concurrent_event_writers_get_unique_sequences(self):
        with tempfile.TemporaryDirectory() as tmp:
            workers = [threading.Thread(target=lambda: [session.append_event(tmp, 'test') for _ in range(8)]) for _ in range(3)]
            for worker in workers: worker.start()
            for worker in workers: worker.join(10)
            self.assertEqual([e['seq'] for e in session.read_events(tmp)], list(range(1, 25)))


class RuntimeTests(unittest.TestCase):
    def test_base_install_does_not_require_every_font(self):
        manifest = bootstrap.load_manifest(bootstrap.DEFAULT_MANIFEST)
        self.assertEqual(bootstrap.scoped_manifest(manifest)['fonts']['files'], [])
        selected = bootstrap.scoped_manifest(manifest, 'rendercv-harvard')
        self.assertGreater(len(selected['fonts']['files']), 0)
        self.assertLess(len(selected['fonts']['files']), len(manifest['fonts']['files']))
        self.assertNotIn('Noto Sans CJK SC', {f['family'] for f in selected['fonts']['files']})

    def test_offline_cache_is_verified_and_never_falls_back_to_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            offline = root / 'offline'
            offline.mkdir()
            source = offline / 'asset.bin'
            source.write_bytes(b'pinned artifact')
            artifact = {'filename': source.name, 'url': 'https://example.invalid/asset.bin', 'sha256': bootstrap.sha256(source)}
            with patch.dict(os.environ, {'RESUME_BUILDER_OFFLINE_DIR': str(offline)}), patch.object(bootstrap, 'urlopen') as network:
                result = bootstrap.download(artifact, root / 'cache', None)
                self.assertEqual(result.read_bytes(), b'pinned artifact')
                artifact['filename'] = 'missing.bin'
                with self.assertRaises(bootstrap.BootstrapError):
                    bootstrap.download(artifact, root / 'cache', None)
                network.assert_not_called()

    def test_typst_timeout_terminates_command(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'RESUME_BUILDER_TYPST_TIMEOUT': '.15'}):
            start = time.monotonic()
            with self.assertRaisesRegex(render.RenderError, '已终止'):
                render.run_typst(sys.executable, ['-c', 'import time; time.sleep(20)'], tmp)
            self.assertLess(time.monotonic() - start, 3)


class ServerRecoveryTests(unittest.TestCase):
    def test_web_save_then_agent_save_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'resume.json'
            data = fixture()
            resume_model.save_resume(path, data)
            core = serve.ServerCore(tmp)
            queued = []
            core.queue_render = lambda reason: queued.append(reason)
            core.save_resume(copy.deepcopy(data))
            data['basics']['headline'] = 'Agent edited after browser save'
            resume_model.save_resume(path, data)
            worker = threading.Thread(target=core._file_watcher)
            worker.start()
            try:
                time.sleep(serve.WATCH_INTERVAL * 3)
            finally:
                core._stop.set()
                worker.join(2)
            self.assertEqual(queued, ['web-save', 'external-resume-change'])

    def test_unexpected_first_render_failure_is_visible_and_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = serve.ServerCore(tmp)
            with patch.object(render, 'render_project', side_effect=PermissionError('Windows test lock')):
                core._render_one('startup')
            state = core.state_summary()
            self.assertFalse(state['rendering'])
            self.assertFalse(state['render']['ok'])
            self.assertIn('Windows test lock', state['error']['message'])
            with patch.object(render, 'render_project', return_value={'ok': True, 'pages': 1, 'fields': 1}):
                core._render_one('api-request')
            self.assertIsNone(core.session['error'])

    def test_second_server_cannot_render_same_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            httpd, core = serve.create_server(tmp, port=0)
            try:
                with self.assertRaises(serve.ServeError):
                    serve.create_server(tmp, port=0)
            finally:
                core.stop_background()
                httpd.server_close()
            httpd, core = serve.create_server(tmp, port=0)
            core.stop_background()
            httpd.server_close()

    def test_retry_cannot_release_an_unadapted_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            resume_model.save_resume(Path(tmp) / 'resume.json', fixture())
            session.set_stage(tmp, 'generating', selected_template='orange-chinese', selected_language='zh')
            core = serve.ServerCore(tmp)
            core._render_one('api-request')
            self.assertEqual(core.session['stage'], 'generating')
            self.assertIn('尚未写入', core.state_summary()['render']['error'])


class ActualRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            render.find_typst()
        except render.RenderError:
            raise unittest.SkipTest('Typst is not installed')

    def test_first_bom_render_and_failed_retry_preserve_preview(self):
        with tempfile.TemporaryDirectory(prefix='简历 测试-') as tmp:
            path = Path(tmp) / 'resume.json'
            path.write_text(json.dumps(fixture()), encoding='utf-8-sig')
            result = render.render_project(tmp)
            pdf = Path(result['build_dir']) / 'resume.pdf'
            original = pdf.read_bytes()
            with patch.object(render, 'check_original_fonts', side_effect=render.RenderError('test font missing')):
                with self.assertRaises(render.RenderError):
                    render.render_project(tmp)
            self.assertEqual(render.current_build_dir(tmp), result['build_dir'])
            self.assertEqual(pdf.read_bytes(), original)
            core = serve.ServerCore(tmp)
            self.assertFalse(core.state_summary()['render']['ok'])
            self.assertTrue(core.read_page_svg(1).startswith(b'<svg'))
            recovered = render.render_project(tmp)
            self.assertTrue(core.state_summary()['render']['ok'])
            self.assertNotEqual(recovered['revision'], result['revision'])
            exported = core.export_pdf()
            self.assertTrue((Path(tmp) / exported['filename']).is_file())
            self.assertEqual(core.session['stage'], 'done')


if __name__ == '__main__':
    unittest.main()
