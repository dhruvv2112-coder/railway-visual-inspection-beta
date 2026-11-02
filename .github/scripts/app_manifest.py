"""latest.json for an Android Beta build: version, notes (one per line), SHA-256 and size of the APK."""
import datetime
import hashlib
import json
import os
import sys

apk, notes_file = sys.argv[1], sys.argv[2]
data = open(apk, "rb").read()
notes = [x.strip() for x in open(notes_file, encoding="utf-8") if x.strip()]
print(json.dumps({"version_code": int(os.environ["VCODE"]), "version_name": os.environ["VNAME"], "notes": notes,
                  "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
                  "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "commit": os.environ.get("GITHUB_SHA", "")},
                 indent=1))
