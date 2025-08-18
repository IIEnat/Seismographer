# Currently this does nothing apart from checking that the frontend can actually use this. No backend has been worked on so far. 
# Will leave this for now but I think all python files will now be in resources/python/

import sys
import time
import json

# Just print immediately
print("Hello from Python!", flush=True)

# Send some JSON
data = {"status": "ok", "value": 123}
print(json.dumps(data), flush=True)

# Optional: stream some output
for i in range(5):
    print(f"tick {i}", flush=True)
    time.sleep(0.5)

sys.exit(0)
