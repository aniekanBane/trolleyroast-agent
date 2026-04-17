#!/usr/bin/env python3
from pathlib import Path
import os

def load_env(path):
    for line in Path(path).read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k,v=line.split('=',1)
        os.environ[k]=v

load_env('trolleyroast-agent/.env')
import test_ingest
