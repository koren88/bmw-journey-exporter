import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix' and shutil.which('sh') and shutil.which('make'), 'POSIX Make shell integration is exercised on macOS/Linux')
class MakeInterfaceTests(unittest.TestCase):
    def run_make(self, target, **variables):
        command = ['make', '--no-print-directory', target]
        command.extend(f'{name}={value}' for name, value in variables.items())
        env = os.environ.copy()
        env['BMW_MAKE_DRY_RUN'] = '1'
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        return result, [line[4:] for line in result.stdout.splitlines() if line.startswith('ARG:')]

    def test_capture_forwards_options_and_preserves_output_spaces(self):
        result, args = self.run_make('capture', YEAR='2026', OUTPUT='./capture with spaces',
                                     SERIAL='device-1', TIMEZONE='Europe/Ljubljana',
                                     PAUSE='2.5', MAX_PAGES='80', KEEP_AWAKE='1',
                                     FORMATS='xlsx,csv', KEEP_CAPTURE='1', KEEP_DEBUG='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(args, ['--output','./capture with spaces','--year','2026','--serial','device-1',
                                '--timezone','Europe/Ljubljana','--pause','2.5','--max-pages','80','--formats','xlsx,csv','--keep-awake','--keep-capture','--keep-debug'])

    def test_capture_without_output_generates_unique_names(self):
        first_result, first = self.run_make('capture', MONTH='2026-10')
        second_result, second = self.run_make('capture', MONTH='2026-10')
        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        first_output=first[first.index('--output')+1]
        second_output=second[second.index('--output')+1]
        self.assertRegex(first_output,r'^\./bmw-export-\d{8}-\d{6}-\d+$')
        self.assertNotEqual(first_output,second_output)

    def test_resume_requires_output_and_forwards_only_explicit_overrides(self):
        with tempfile.TemporaryDirectory(prefix='capture with spaces ') as output:
            result,args=self.run_make('resume',OUTPUT=output,TIMEZONE='Europe/Ljubljana',KEEP_AWAKE='0')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(args,['--resume','--output',output,'--timezone','Europe/Ljubljana','--no-keep-awake'])
        result,_=self.run_make('resume')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('requires OUTPUT',result.stderr)

    def test_report_and_merge_keep_paths_with_spaces(self):
        result,args=self.run_make('report',INPUT='./capture with spaces')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(args,['--report-only','./capture with spaces'])
        result,args=self.run_make('merge',INPUTS='./first capture:./second capture',OUTPUT='./merged capture',CONFLICT='keep-last')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(args,['--merge','./first capture','--merge','./second capture','--output','./merged capture','--conflict','keep-last'])

    def test_merge_forwards_retention_true_and_false_values(self):
        result,args=self.run_make('merge',INPUTS='./first:./second',OUTPUT='./merged',KEEP_CAPTURE='yes',KEEP_DEBUG='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(args[-2:],['--keep-capture','--keep-debug'])
        result,args=self.run_make('merge',INPUTS='./first:./second',OUTPUT='./merged',KEEP_CAPTURE='false',KEEP_DEBUG='0')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(args[-2:],['--no-keep-capture','--no-keep-debug'])

    def test_merge_rejects_invalid_retention_values(self):
        result,_=self.run_make('merge',INPUTS='./first:./second',OUTPUT='./merged',KEEP_CAPTURE='sometimes')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('KEEP_CAPTURE must be',result.stderr)


@unittest.skipUnless(os.name == 'posix' and shutil.which('sh') and shutil.which('make'), 'POSIX Make shell integration is exercised on macOS/Linux')
class MakeTestEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / 'Makefile', self.root / 'Makefile')
        shutil.copy(ROOT / 'make-cli.sh', self.root / 'make-cli.sh')
        self.make = shutil.which('make')
        if not self.make:
            self.skipTest('GNU Make is unavailable')
        self.fakebin = self.root / 'fakebin'
        self.fakebin.mkdir()
        self.log = self.root / 'calls.log'
        launcher = self.root / 'docker-launch.sh'
        launcher.write_text('#!/bin/sh\nprintf "docker:%s\\n" "$1" >> "$TEST_LOG"\nexit 0\n', encoding='utf-8')
        launcher.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def python_stub(self, path, name, usable):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '#!/bin/sh\n'
            f'if [ "$1" = "-c" ]; then echo "{name}:probe" >> "$TEST_LOG"; exit {0 if usable else 1}; fi\n'
            f'echo "{name}:run" >> "$TEST_LOG"\n'
            'exit 0\n'
        , encoding='utf-8')
        path.chmod(0o755)
        return path

    def run_test_target(self, *, python_override=None, docker=False):
        env = {'PATH': str(self.fakebin), 'TEST_LOG': str(self.log)}
        if python_override is not None:
            env['PYTHON'] = str(python_override)
        if docker:
            docker_stub = self.fakebin / 'docker'
            docker_stub.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
            docker_stub.chmod(0o755)
        result = subprocess.run([self.make, '--no-print-directory', 'test'], cwd=self.root,
                                env=env, text=True, capture_output=True)
        calls = self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []
        return result, calls

    def test_uses_project_venv_before_global_python_or_docker(self):
        self.python_stub(self.fakebin / 'python3', 'global', False)
        self.python_stub(self.root / '.venv/bin/python', 'venv', True)
        result, calls = self.run_test_target()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['venv:probe', 'venv:run'])

    def test_explicit_python_override_takes_precedence_over_project_venv(self):
        self.python_stub(self.root / '.venv/bin/python', 'venv', True)
        override = self.python_stub(self.fakebin / 'custom-python', 'override', True)
        result, calls = self.run_test_target(python_override=override)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['override:probe', 'override:run'])

    def test_docker_fallback_when_no_python_environment_is_usable(self):
        self.python_stub(self.fakebin / 'python3', 'global', False)
        result, calls = self.run_test_target(docker=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['global:probe', 'docker:test'])

    def test_clear_failure_when_python_and_docker_are_unavailable(self):
        self.python_stub(self.fakebin / 'python3', 'global', False)
        result, calls = self.run_test_target()
        self.assertEqual(result.returncode, 2)
        self.assertIn('Run make setup', result.stderr)
        self.assertEqual(calls, ['global:probe'])

    def test_report_path_is_preserved_under_project_docker_mount(self):
        uname = self.fakebin / 'uname'
        uname.write_text('#!/bin/sh\necho Linux\n', encoding='utf-8')
        uname.chmod(0o755)
        docker_log = self.root / 'docker.log'
        docker = self.fakebin / 'docker'
        docker.write_text(
            '#!/bin/sh\n'
            'printf "CALL" >> "$DOCKER_LOG"\n'
            'for arg do printf "\\nARG:%s" "$arg" >> "$DOCKER_LOG"; done\n'
            'printf "\\n" >> "$DOCKER_LOG"\n'
            'case "$1" in image) exit 1 ;; build|run) exit 0 ;; esac\n'
            'exit 1\n'
        , encoding='utf-8')
        docker.chmod(0o755)
        env = os.environ.copy()
        env.update(PATH=f'{self.fakebin}:{env["PATH"]}', DOCKER_LOG=str(docker_log))
        with tempfile.TemporaryDirectory(prefix='launcher report ',dir=ROOT) as input_dir:
            result = subprocess.run([self.make, '--no-print-directory', 'report',
                                     f'INPUT=./{Path(input_dir).name}'],
                                    cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = docker_log.read_text(encoding='utf-8')
            self.assertIn(f'ARG:{ROOT}:/workspace', calls)
            self.assertIn('ARG:-w\nARG:/workspace', calls)
            self.assertIn(f'ARG:--report-only\nARG:/workspace/{Path(input_dir).name}', calls)


if __name__ == '__main__':
    unittest.main()
