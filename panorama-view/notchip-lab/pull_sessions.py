"""Copy the debug app's local sessions using adb, without PowerShell binary redirection.

No device files are deleted. New destination only. Extracts regular files / dirs
under files/sweeps; refuses links and traversal. Android USB authorization required.
"""
from pathlib import Path, PurePosixPath
import argparse
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent


def pull(destination: Path):
    destination = destination.resolve()
    if not destination.is_relative_to(ROOT / 'artifacts') or destination.exists():
        raise ValueError('Choose a new directory inside notchip-lab/artifacts')
    destination.mkdir(parents=True)
    payload = destination / 'device-sessions.tar'
    with payload.open('xb') as stream:
        subprocess.run(['adb', 'exec-out', 'run-as', 'com.rentlease.notchiplab',
                        'tar', '-cf', '-', 'files/sweeps'], stdout=stream, check=True)
    with tarfile.open(payload) as bundle:
        for member in bundle.getmembers():
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or '..' in relative.parts or
                    relative.parts[:2] != ('files', 'sweeps') or
                    not (member.isfile() or member.isdir())):
                raise ValueError(f'Unsafe device entry: {member.name}')
        bundle.extractall(destination, filter='data')
    print(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    pull(parser.parse_args().destination)
