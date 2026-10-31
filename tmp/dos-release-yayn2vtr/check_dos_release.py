"""Read-only compatibility check. Run from the extracted DOS package."""
import hashlib
import json
from pathlib import Path
import sys

package = Path(__file__).resolve().parent
target = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else None
if target is None or not (target / 'manage.py').is_file():
    raise SystemExit('Usage: python check_dos_release.py /path/to/existing/application')
manifest = json.loads((package / 'DOS_RELEASE_MANIFEST.json').read_text())
def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() if path.is_file() else None
conflicts = []
for name, hashes in manifest.items():
    if digest(package / name) != hashes['after']:
        conflicts.append(name + ': package integrity mismatch')
    elif digest(target / name) not in (hashes['before'], hashes['after']):
        conflicts.append(name + ': hosting differs from supported baseline; do not overwrite')
if conflicts:
    print('CHECK FAILED. No files changed.')
    print('\n'.join(conflicts))
    raise SystemExit(1)
print('CHECK PASSED. Compatible DOS update. No files changed.')
