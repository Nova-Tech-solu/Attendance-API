"""
Run this script to generate a new office API key.
Give the raw key to the office (.exe config).
Put the hash in your Render environment variable.

Usage:
    python generate_key.py provost
    python generate_key.py registry
"""

import sys
import hashlib
import secrets

if len(sys.argv) < 2:
    print("Usage: python generate_key.py <office_slug>")
    sys.exit(1)

slug = sys.argv[1].upper()
raw_key = secrets.token_hex(32)
hashed = hashlib.sha256(raw_key.encode()).hexdigest()

print(f"\n{'='*60}")
print(f"  Office:       {slug}")
print(f"  Raw API Key:  {raw_key}")
print(f"  (Give this key to the .exe config for this office)")
print(f"\n  Env Var Name: OFFICE_KEY_{slug}")
print(f"  Env Var Value (hash): {hashed}")
print(f"  (Put this in Render/Railway environment variables)")
print(f"{'='*60}\n")