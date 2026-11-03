"""Prepare an Android SDK inside this experiment. Official repository + checksum.

Requires JAVA_HOME (Java 17), internet and consent to displayed Android SDK
licenses. Does not change a system SDK, PATH or registry.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
SDK = ROOT / 'android-sdk'


def main():
    java = ROOT / 'jdk17'
    env = os.environ.copy()
    if (java / 'bin/java.exe').is_file():
        env['JAVA_HOME'] = str(java)
    env['ANDROID_USER_HOME'] = str(SDK / '.android')
    # Pin the classic manager: current 'latest' delegates to a different CLI.
    manager = SDK / 'cmdline-tools/19.0/bin/sdkmanager.bat'
    if not manager.exists():
        print('Reading official Android SDK repository', flush=True)
        with urllib.request.urlopen('https://dl.google.com/android/repository/repository2-1.xml') as response:
            repository = ET.fromstring(response.read())
        package = next(p for p in repository.findall('remotePackage') if p.get('path') == 'cmdline-tools;19.0')
        item = next(a.find('complete') for a in package.findall('archives/archive') if a.findtext('host-os') == 'windows')
        filename = item.findtext('url')
        checksum = item.find('checksum')
        algorithm = checksum.get('type', 'sha1').replace('-', '').lower()
        downloads = ROOT / 'downloads'; downloads.mkdir(exist_ok=True)
        payload = downloads / filename
        if not payload.exists():
            with urllib.request.urlopen('https://dl.google.com/android/repository/' + filename) as source, payload.open('xb') as out:
                shutil.copyfileobj(source, out)
        with payload.open('rb') as stream:
            digest = hashlib.file_digest(stream, algorithm).hexdigest()
        if digest != checksum.text:
            raise ValueError('Official SDK checksum mismatch; refusing extraction')
        print(f'Verified {filename}: {algorithm} {digest}', flush=True)
        destination = SDK / 'cmdline-tools/19.0'
        with zipfile.ZipFile(payload) as bundle:
            for member in bundle.infolist():
                parts = Path(member.filename).parts
                if parts[0] != 'cmdline-tools':
                    raise ValueError('Unexpected SDK zip root')
                target = destination.joinpath(*parts[1:]).resolve()
                if not target.is_relative_to(destination):
                    raise ValueError('Unsafe SDK entry')
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, target.open('xb') as out:
                        shutil.copyfileobj(source, out)
    # Interactive: user reads and accepts SDK licenses through sdkmanager.
    subprocess.run([str(manager), f'--sdk_root={SDK}', 'platform-tools', 'platforms;android-36',
                    'build-tools;36.0.0', 'build-tools;35.0.0',
                    'ndk;27.1.12297006', 'cmake;3.22.1'], env=env, check=True)
    from prepare_ninja import main as prepare_ninja
    prepare_ninja()
    print(f'SDK ready: {SDK}')


if __name__ == '__main__':
    main()
