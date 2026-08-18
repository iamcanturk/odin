#!/usr/bin/env python3
"""Insert a `location /api/` reverse-proxy block (→ 127.0.0.1:8000) into the CloudPanel
vhost, before the catch-all `location / {`. Idempotent. Run as root.

NOTE: CloudPanel may regenerate the vhost when site settings change. To persist, also
paste the same block into CloudPanel → Sites → odin.iamcanturk.dev → Vhost editor.
"""

import subprocess
import sys

VHOST = "/etc/nginx/sites-enabled/odin.iamcanturk.dev.conf"

BLOCK = """  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
  }

"""

src = open(VHOST).read()
if "location /api/" in src:
    print("/api location already present — nothing to do")
    sys.exit(0)

marker = "  location / {"
if marker not in src:
    print("ERROR: could not find 'location / {' anchor", file=sys.stderr)
    sys.exit(1)

open(VHOST + ".odinbak", "w").write(src)
open(VHOST, "w").write(src.replace(marker, BLOCK + marker, 1))
print("inserted /api location; backup at", VHOST + ".odinbak")

test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
print(test.stderr.strip())
if test.returncode != 0:
    open(VHOST, "w").write(src)  # rollback
    print("nginx -t FAILED — rolled back", file=sys.stderr)
    sys.exit(1)
subprocess.run(["systemctl", "reload", "nginx"], check=True)
print("nginx reloaded OK")
