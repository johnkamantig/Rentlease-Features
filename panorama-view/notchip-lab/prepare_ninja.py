"""Upgrade only this lab SDK's Ninja; retain the original. No registry changes.

Ninja >=1.12 supports Windows long paths. CMake 3.22.1 bundles Ninja 1.10.2,
which can build once but fail when stat-ing cached React Native headers later.
"""
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '1.13.2'
SHA256 = '07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65'


def main():
    binary = ROOT / 'android-sdk/cmake/3.22.1/bin/ninja.exe'
    current = subprocess.check_output([str(binary), '--version'], text=True).strip()
    if current == VERSION:
        print(f'Local Ninja {VERSION} already prepared')
        return
    if current != '1.10.2':
        raise ValueError(f'Unexpected local SDK Ninja {current}; refusing replacement')
    with urllib.request.urlopen(f'https://github.com/ninja-build/ninja/releases/download/v{VERSION}/ninja-win.zip') as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != SHA256:
        raise ValueError('Ninja release ZIP SHA-256 mismatch')
    backup = binary.with_name('ninja-1.10.2.exe')
    if backup.exists():
        raise ValueError('Original Ninja backup exists; refusing conflicting replacement')
    with binary.open('rb') as src, backup.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
        binary.write_bytes(bundle.read('ninja.exe'))
    subprocess.run([str(binary), '--version'], check=True)
    print('Updated only the lab SDK; original preserved as ninja-1.10.2.exe')


if __name__ == '__main__':
    main()
