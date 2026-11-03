"""Sample Android process PSS. Observed maximum is not a true native peak."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parent


def measure(destination: Path):
    destination = destination.resolve()
    if not destination.is_relative_to(ROOT / 'artifacts'):
        raise ValueError('Write measurements inside notchip-lab/artifacts')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as out:
        try:
            while True:
                tick = time.time()
                result = subprocess.run(['adb', 'shell', 'dumpsys', 'meminfo',
                                         'com.rentlease.notchiplab'], capture_output=True, text=True, check=True)
                match = re.search(r'TOTAL PSS:\s*(\d+)', result.stdout)
                if not match:
                    match = re.search(r'^\s*TOTAL\s+(\d+)', result.stdout, re.M)
                out.write(json.dumps({'unixSeconds': tick,
                                      'pssKiB': int(match[1]) if match else None,
                                      'raw': result.stdout}) + '\n')
                out.flush()
                time.sleep(max(0, 1-(time.time()-tick)))
        except KeyboardInterrupt:
            pass
    print(f'Samples saved to {destination}; report observed maximum, not true peak.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    measure(parser.parse_args().destination)
