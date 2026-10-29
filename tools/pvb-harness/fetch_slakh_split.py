#!/usr/bin/env python3
"""Keep one split of Slakh2100-redux (Zenodo 4599666, CC BY 4.0) without storing the 104 GB archive (#4).

The archive is read as a stream (from the record URL, reconnecting with a byte range after a dropped connection, or
from a local file) and only the members under <top>/<split>/ are written; everything else is read and discarded. The
MD5 of every archive byte is checked against the record at the end. Local use only: no audio is committed.
"""
import argparse
import hashlib
import http.client
import io
import sys
import tarfile
import time
import urllib.request
from pathlib import Path, PurePosixPath

URL = 'https://zenodo.org/records/4599666/files/slakh2100_flac_redux.tar.gz?download=1'
SIZE, MD5 = 104322767708, 'f4b71b6c45ac9b506f59788456b3f0c4'


class Source(io.RawIOBase):
    """Archive bytes in order, hashed as they pass; a URL reconnects from the current byte after an error."""

    def __init__(self, where):
        self.where = where; self.pos = 0; self.md5 = hashlib.md5(); self.r = None; self.last = 0.

    def readable(self): return True

    def _open(self):
        if not self.where.startswith('https://'):
            self.r = open(self.where, 'rb'); self.r.seek(self.pos); return
        hdr = {'Range': f'bytes={self.pos}-'} if self.pos else {}
        self.r = urllib.request.urlopen(urllib.request.Request(self.where, headers=hdr), timeout=120)
        if self.pos and self.r.status != 206: raise OSError(f'range not honoured (HTTP {self.r.status})')

    def readinto(self, b):
        for attempt in range(200):
            try:
                if self.r is None: self._open()
                n = self.r.readinto(b)
                if n == 0 and self.where.startswith('https://') and self.pos < SIZE: raise OSError('connection ended early')
                self.md5.update(memoryview(b)[:n]); self.pos += n
                if time.time() - self.last > 300:
                    self.last = time.time(); print(f'{time.strftime("%F %T")} {self.pos / 1e9:.2f} / {SIZE / 1e9:.2f} GB', flush=True)
                return n
            except (OSError, http.client.HTTPException) as e:
                print(f'{time.strftime("%F %T")} reconnect at {self.pos} ({e})', flush=True)
                self.r = None; time.sleep(min(120, 10 * (attempt + 1)))
        raise OSError('gave up after 200 reconnects')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out', type=Path, help='empty folder for the kept split')
    p.add_argument('--source', default=URL, help='record URL (default) or a local copy of the archive')
    p.add_argument('--split', default='test')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    src = Source(a.source); kept = 0; tracks = set()
    with tarfile.open(fileobj=io.BufferedReader(src, 1 << 20), mode='r|gz') as tf:
        for m in tf:
            parts = PurePosixPath(m.name).parts
            if len(parts) < 3 or parts[1] != a.split or not m.isfile(): continue
            if any(x in ('', '.', '..') for x in parts) or PurePosixPath(m.name).is_absolute(): raise SystemExit(f'unsafe path {m.name}')
            dst = a.out.joinpath(*parts[1:]); dst.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(m) as f, open(dst, 'wb') as g:
                while chunk := f.read(1 << 20): g.write(chunk)
            kept += 1; tracks.add(parts[2])
    buf = bytearray(1 << 20)
    while src.readinto(buf): pass   # the bytes after the tar end still count for the MD5
    got = src.md5.hexdigest()
    print(f'kept {kept} files in {len(tracks)} {a.split} tracks; read {src.pos} bytes; md5 {got}', flush=True)
    if a.source.startswith('https://') or src.pos == SIZE:
        ok = src.pos == SIZE and got == MD5
        print('MD5 OK' if ok else f'MD5 MISMATCH (want {MD5}, {SIZE} bytes)', flush=True)
        sys.exit(0 if ok else 3)


if __name__ == '__main__':
    main()
