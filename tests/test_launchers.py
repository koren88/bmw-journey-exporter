import os
import shutil
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix' and shutil.which('sh'), 'POSIX launcher integration requires a POSIX shell')
class DockerLauncherTests(unittest.TestCase):
    def fake_linux(self, fakebin):
        uname=fakebin/'uname'
        uname.write_text('#!/bin/sh\nprintf "Linux\\n"\n', encoding='utf-8')
        uname.chmod(0o755)

    def fake_offline_docker(self, fakebin):
        docker=fakebin/'docker'
        docker.write_text('''#!/bin/sh
case "$1" in
  image) exit 1 ;;
  build) exit 0 ;;
  run)
    printf 'RUN\\n' >> "$FAKE_DOCKER_LOG"
    for arg do printf 'ARG:%s\\n' "$arg" >> "$FAKE_DOCKER_LOG"; done
    exit 0 ;;
esac
exit 1
''', encoding='utf-8')
        docker.chmod(0o755)

    def test_linux_launcher_requires_explicit_adb_host_and_forwards_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); fakebin=tmp/'bin'; fakebin.mkdir()
            log=tmp/'docker.log'
            docker=fakebin/'docker'
            docker.write_text('''#!/bin/sh
case "$1" in
  image) exit 1 ;;
  build) exit 0 ;;
  run)
    printf 'RUN\\n' >> "$FAKE_DOCKER_LOG"
    for arg do printf 'ARG:%s\\n' "$arg" >> "$FAKE_DOCKER_LOG"; done
    exit 0 ;;
esac
exit 1
''', encoding='utf-8')
            docker.chmod(0o755)
            self.fake_linux(fakebin)
            env=os.environ.copy(); env.update(PATH=f'{fakebin}:{env["PATH"]}',FAKE_DOCKER_LOG=str(log),BMW_ADB_HOST='127.0.0.1',BMW_ADB_PORT='5037')
            result=subprocess.run([str(ROOT/'docker-linux.sh'),'--doctor','--serial','device with spaces'],cwd=ROOT,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            blocks=log.read_text(encoding='utf-8').split('RUN\n')
            self.assertEqual(len(blocks),3)  # probe, then final CLI container
            final=[line[4:] for line in blocks[-1].splitlines() if line.startswith('ARG:')]
            self.assertIn('--network',final)
            self.assertIn('host',final)
            user_index=final.index('--user')
            self.assertEqual(final[user_index+1],f'{os.getuid()}:{os.getgid()}')
            self.assertIn('ADB_SERVER_SOCKET=tcp:127.0.0.1:5037',final)
            self.assertIn('--doctor',final)
            serial_index=final.index('--serial')
            self.assertEqual(final[serial_index+1],'device with spaces')

            output=ROOT/'capture with spaces'
            result=subprocess.run([str(ROOT/'docker-linux.sh'),'--month','2026-10','--formats','xlsx,csv',
                                    '--keep-capture','--keep-debug','--output',str(output)],
                                   cwd=ROOT,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            blocks=log.read_text(encoding='utf-8').split('RUN\n')
            final=[line[4:] for line in blocks[-1].splitlines() if line.startswith('ARG:')]
            for expected in ('--month','2026-10','--formats','xlsx,csv','--keep-capture','--keep-debug','--output','/workspace/capture with spaces'):
                self.assertIn(expected,final)

            with tempfile.TemporaryDirectory(prefix='launcher path ',dir=ROOT) as input_dir:
                result=subprocess.run([str(ROOT/'docker-linux.sh'),'--report-only',input_dir],cwd=ROOT,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                blocks=log.read_text(encoding='utf-8').split('RUN\n')
                final=[line[4:] for line in blocks[-1].splitlines() if line.startswith('ARG:')]
                self.assertEqual(final[-2:],['--report-only',f"/workspace/{Path(input_dir).name}"])

    def test_external_report_paths_are_rejected_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            fakebin=Path(tmp)/'bin'; fakebin.mkdir(); log=Path(tmp)/'docker.log'
            docker=fakebin/'docker'; docker.write_text('#!/bin/sh\nprintf called >> "$FAKE_DOCKER_LOG"\nexit 0\n', encoding='utf-8'); docker.chmod(0o755)
            self.fake_linux(fakebin)
            external=Path(tmp)/'external capture'; external.mkdir()
            env=os.environ.copy(); env.update(PATH=f'{fakebin}:{env["PATH"]}',FAKE_DOCKER_LOG=str(log))
            result=subprocess.run([str(ROOT/'docker-linux.sh'),'--report-only',str(external)],cwd=ROOT,env=env,text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('outside the mounted repository',result.stderr)
            self.assertIn('local Python CLI',result.stderr)
            self.assertFalse(log.exists())

    def test_abbreviated_output_options_are_rejected_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            fakebin=Path(tmp)/'bin'; fakebin.mkdir(); log=Path(tmp)/'docker.log'
            self.fake_offline_docker(fakebin); self.fake_linux(fakebin)
            env=os.environ.copy(); env.update(PATH=f'{fakebin}:{env["PATH"]}',FAKE_DOCKER_LOG=str(log))
            for option in ('--out', '--out=/tmp/example'):
                result=subprocess.run([str(ROOT/'docker-linux.sh'),option],cwd=ROOT,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,2,option)
                self.assertIn('Use --output PATH',result.stderr)
            self.assertFalse(log.exists(), 'unsupported abbreviated output reached docker run')

    def test_cli_disables_argparse_long_option_abbreviations(self):
        for option in ('--out', '--out=/tmp/example'):
            result=subprocess.run([sys.executable,str(ROOT/'bmw_export_journeys.py'),option],cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(result.returncode,2,option)
            self.assertIn('unrecognized arguments',result.stderr)

    def test_equals_offline_options_skip_adb_and_linux_offline_runs_as_invoking_user(self):
        with tempfile.TemporaryDirectory() as tmp, \
             tempfile.TemporaryDirectory(prefix='offline report ',dir=ROOT) as report_dir, \
             tempfile.TemporaryDirectory(prefix='offline merge a ',dir=ROOT) as first, \
             tempfile.TemporaryDirectory(prefix='offline merge b ',dir=ROOT) as second, \
             tempfile.TemporaryDirectory(prefix='offline merged ',dir=ROOT) as output:
            fakebin=Path(tmp)/'bin'; fakebin.mkdir(); log=Path(tmp)/'docker.log'
            self.fake_offline_docker(fakebin); self.fake_linux(fakebin)
            env=os.environ.copy(); env.update(PATH=f'{fakebin}:{env["PATH"]}',FAKE_DOCKER_LOG=str(log))
            env.pop('BMW_ADB_HOST',None)
            commands=(
                [str(ROOT/'docker-linux.sh'),f'--report-only={report_dir}'],
                [str(ROOT/'docker-linux.sh'),'--report-only',report_dir],
                [str(ROOT/'docker-linux.sh'),f'--merge={first}',f'--merge={second}',f'--output={output}'],
                [str(ROOT/'docker-linux.sh'),'--merge',first,'--merge',second,'--output',output],
            )
            for command in commands:
                result=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
            blocks=log.read_text(encoding='utf-8').split('RUN\n')
            self.assertEqual(len(blocks),5, 'offline commands should each execute one container, without an ADB probe')
            expected_user=f'{os.getuid()}:{os.getgid()}'
            for block in blocks[1:]:
                args=[line[4:] for line in block.splitlines() if line.startswith('ARG:')]
                self.assertIn('--user',args)
                self.assertEqual(args[args.index('--user')+1],expected_user)
            report_args=[line[4:] for line in blocks[1].splitlines() if line.startswith('ARG:')]
            self.assertIn(f'--report-only=/workspace/{Path(report_dir).name}',report_args)
            separated_report_args=[line[4:] for line in blocks[2].splitlines() if line.startswith('ARG:')]
            self.assertEqual(separated_report_args[-2:],['--report-only',f'/workspace/{Path(report_dir).name}'])
            for block in blocks[3:]:
                merge_args=[line[4:] for line in block.splitlines() if line.startswith('ARG:')]
                expected=[f'/workspace/{Path(first).name}',f'/workspace/{Path(second).name}']
                if any(arg.startswith('--merge=') for arg in merge_args):
                    self.assertEqual([arg.split('=',1)[1] for arg in merge_args if arg.startswith('--merge=')],expected)
                else:
                    self.assertEqual([merge_args[i+1] for i,arg in enumerate(merge_args[:-1]) if arg == '--merge'],expected)

    def test_recovery_commands_keep_host_paths_through_launcher_cli_boundary(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory(prefix='launcher recovery ',dir=ROOT) as output_root:
            base=Path(tmp); fakebin=base/'bin'; fakebin.mkdir(); log=base/'docker.log'
            driver=base/'driver.py'
            driver.write_text(textwrap.dedent(f'''\
                import os, sys
                from pathlib import Path
                from unittest import mock
                import bmw_export_journeys as app
                root=Path({str(ROOT)!r})
                args=sys.argv[1:]
                for i, value in enumerate(args):
                    if value == '--output' and i+1 < len(args) and args[i+1].startswith('/workspace/'):
                        args[i+1]=str(root / args[i+1][len('/workspace/'):])
                    elif value.startswith('--output=/workspace/'):
                        args[i]='--output='+str(root / value[len('--output=/workspace/'):])
                sys.argv=['cli',*args]
                mode=os.environ['BMW_TEST_CASE']
                def fake_capture(exporter):
                    if mode == 'interrupted': raise KeyboardInterrupt('mock interruption')
                    if mode == 'report-failure':
                        for report in exporter.reports:
                            report.update(status='complete',expected_trip_count=0)
                def fake_reports(folder,replacements,formats):
                    if mode == 'report-failure': raise OSError('mock report failure')
                    (Path(folder)/'journeys.xlsx').write_text('mock report',encoding='utf-8')
                with mock.patch.object(app,'adb_devices',return_value=[['MOCK','device']]), \\
                     mock.patch.object(app.Exporter,'run',fake_capture), \\
                     mock.patch.object(app,'build_reports',side_effect=fake_reports):
                    raise SystemExit(app.main())
            '''), encoding='utf-8')
            docker=fakebin/'docker'
            docker.write_text(f'''#!/bin/sh
case "$1" in image) exit 1 ;; build) exit 0 ;; esac
while [ "$#" -gt 0 ] && [ "$1" != bmw-journey-exporter ]; do shift; done
[ "$#" -gt 0 ] || exit 90
shift
[ "${{1:-}}" != -c ] || exit 0
PYTHONPATH="{ROOT}" exec "{sys.executable}" "{driver}" "$@"
''', encoding='utf-8')
            docker.chmod(0o755); self.fake_linux(fakebin)
            env=os.environ.copy()
            env.update(PATH=f'{fakebin}:{env["PATH"]}',FAKE_DOCKER_LOG=str(log),BMW_ADB_HOST='127.0.0.1',BMW_TEST_CASE='interrupted')
            env.pop('BMW_ADB_PORT',None)
            for case in ('interrupted','incomplete','report-failure'):
                output=f"./{Path(output_root).name}/O'Brien capture-{case}"
                env['BMW_TEST_CASE']=case
                result=subprocess.run([str(ROOT/'docker-linux.sh'),'--month','2026-10','--output',output],cwd=ROOT,env=env,text=True,capture_output=True)
                self.assertNotEqual(result.returncode,0,case)
                combined=result.stdout+'\n'+result.stderr
                command_lines=[line for line in combined.splitlines()
                               if line.startswith(('Resume command:', 'Report retry:', 'Report retry (local Python):'))]
                self.assertTrue(command_lines,case)
                self.assertTrue(all('/workspace/' not in line for line in command_lines),case)
                parsed=[(line.split(': ',1)[0],shlex.split(line.split(': ',1)[1])) for line in command_lines]
                labels={label for label,_ in parsed}
                self.assertEqual(labels, {'Resume command'} if case != 'report-failure' else
                                 {'Resume command','Report retry','Report retry (local Python)'})
                for label,argv in parsed:
                    if label == 'Resume command' and argv[:2] == ['make','resume']:
                        self.assertEqual(argv[2:],['OUTPUT='+output])
                    elif label == 'Resume command':
                        self.assertEqual(argv[:4],['python3','bmw_export_journeys.py','--resume','--output'])
                        self.assertEqual(argv[4:],[output])
                    elif label == 'Report retry':
                        self.assertEqual(argv[:2],['make','report'])
                        self.assertEqual(argv[2],'INPUT='+output)
                    else:
                        self.assertEqual(argv[:3],['python3','bmw_export_journeys.py','--report-only'])
                        self.assertEqual(argv[3],output)
                if case == 'report-failure':
                    self.assertTrue(any(label == 'Resume command' for label,_ in parsed))

    def test_external_merge_input_and_output_are_rejected_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory(prefix='launcher merge ',dir=ROOT) as inside:
            fakebin=Path(tmp)/'bin'; fakebin.mkdir(); log=Path(tmp)/'docker.log'
            docker=fakebin/'docker'; docker.write_text('#!/bin/sh\nprintf called >> "$FAKE_DOCKER_LOG"\nexit 0\n', encoding='utf-8'); docker.chmod(0o755)
            self.fake_linux(fakebin)
            external=Path(tmp)/'external capture'; external.mkdir()
            env=os.environ.copy(); env.update(PATH=f'{fakebin}:{env["PATH"]}',FAKE_DOCKER_LOG=str(log))
            calls=([str(ROOT/'docker-linux.sh'),'--merge',str(external),'--output',str(Path(inside)/'merged')],
                   [str(ROOT/'docker-linux.sh'),'--merge',inside,'--output',str(external/'merged')])
            for command in calls:
                result=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('outside the mounted repository',result.stderr)
            self.assertFalse(log.exists())

    def test_external_symlink_and_parent_traversal_outputs_are_rejected_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory(prefix='launcher symlink ',dir=ROOT) as inside:
            fakebin=Path(tmp)/'bin'; fakebin.mkdir(); log=Path(tmp)/'docker.log'
            docker=fakebin/'docker'; docker.write_text('#!/bin/sh\nprintf called >> "$FAKE_DOCKER_LOG"\nexit 0\n', encoding='utf-8'); docker.chmod(0o755)
            self.fake_linux(fakebin)
            outside=Path(tmp)/'outside'; outside.mkdir()
            link=Path(inside)/'external-link'; link.symlink_to(outside,target_is_directory=True)
            dangling=Path(inside)/'dangling-link'; dangling.symlink_to(outside/'not-created',target_is_directory=True)
            env=os.environ.copy(); env.update(PATH=f'{fakebin}:{env["PATH"]}',FAKE_DOCKER_LOG=str(log))
            cases=((str(link),'outside the mounted repository'),
                   (str(dangling/'new-output'),'dangling symlink'),
                   (str(ROOT/'..'/'outside-output'),'outside the mounted repository'))
            for output, expected_message in cases:
                result=subprocess.run([str(ROOT/'docker-linux.sh'),'--month','2026-10','--output',output],cwd=ROOT,env=env,text=True,capture_output=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(expected_message,result.stderr)
            self.assertFalse(log.exists())

    def test_linux_capture_refuses_missing_adb_host_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            fakebin=Path(tmp)/'bin'; fakebin.mkdir()
            docker=fakebin/'docker'; docker.write_text('#!/bin/sh\ncase "$1" in image) exit 1 ;; build) exit 0 ;; *) exit 99 ;; esac\n', encoding='utf-8'); docker.chmod(0o755)
            self.fake_linux(fakebin)
            env=os.environ.copy(); env['PATH']=f'{fakebin}:{env["PATH"]}'; env.pop('BMW_ADB_HOST',None)
            result=subprocess.run([str(ROOT/'docker-linux.sh'),'--doctor'],cwd=ROOT,env=env,text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Set BMW_ADB_HOST',result.stderr)


if __name__ == '__main__':
    unittest.main()
