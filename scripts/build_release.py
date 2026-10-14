#!/usr/bin/env python3
"""Build a clean source ZIP from an explicit set; reject tracked private state."""
from __future__ import annotations
import argparse
import hashlib
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = {'.venv','state','demo-state','work','__pycache__','.git','dist','node_modules','build','coverage','.pytest_cache'}
DIRECTORIES = {'appsort','bin','codex-skill','docs','examples','helper','licenses','scripts','tests','web','.github'}
FILES = {'README.md','README.zh-CN.md','LICENSE','THIRD_PARTY_NOTICES.md','requirements.txt',
         '.gitignore','CHANGELOG.md','CONTRIBUTING.md','SECURITY.md','Start AppSort.command','Setup AppSort.command'}

def source_files() -> list[Path]:
    tracked = subprocess.run(['git','ls-files'], cwd=ROOT, capture_output=True, text=True)
    if tracked.returncode == 0:
        forbidden = [p for p in tracked.stdout.splitlines() if set(Path(p).parts)&PRIVATE or any(part.startswith('.env') for part in Path(p).parts) or Path(p).suffix in {'.plist','.log','.db','.sqlite','.sqlite3','.segb'} or p=='bin/appsort-usage-helper']
        if forbidden:
            raise ValueError('Private/runtime files are tracked: '+', '.join(forbidden))
    found=[]
    for base,dirs,names in os.walk(ROOT,followlinks=False):
        dirs[:]=[d for d in dirs if d not in PRIVATE]
        for name in names:
            path=Path(base)/name
            relative=path.relative_to(ROOT)
            if relative.parts[0] not in DIRECTORIES and str(relative) not in FILES:
                continue
            if (str(relative)=='bin/appsort-usage-helper' or path.is_symlink() or name.startswith('.env')
                    or name=='.DS_Store' or path.suffix in {'.pyc','.plist','.log','.db','.sqlite','.sqlite3','.segb'}):
                continue
            found.append(path)
    for required in ('README.md','README.zh-CN.md','LICENSE','bin/setup','bin/appsort','appsort/core.py','web/index.html'):
        if ROOT/required not in found:
            raise ValueError('Missing required source: '+required)
    return sorted(found)

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--version',default='0.1.0')
    args=parser.parse_args()
    files=source_files()
    if args.check_only:
        print(f'{len(files)} clean source files; no tracked private/runtime state.')
        return
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    archive=dist/f'iphone-appsort-{args.version}-source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path,f'iphone-appsort-{args.version}/'+str(path.relative_to(ROOT)))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('ZIP checksum validation failed')
    checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist/'SHA256SUMS.txt').write_text(checksum+'  '+archive.name+'\n')
    print(archive)
    print(checksum)

if __name__=='__main__':
    main()
