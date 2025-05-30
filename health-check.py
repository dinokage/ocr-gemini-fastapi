#!/usr/bin/env python3

import sys
import urllib.request
import urllib.error
import json

def health_check():
    try:
        with urllib.request.urlopen('http://localhost:8000/health', timeout=5) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())
                if data.get('status') == 'healthy':
                    print("Health check passed")
                    return True
                else:
                    print(f"Health check failed: {data}")
                    return False
            else:
                print(f"Health check failed with status code: {response.getcode()}")
                return False
    except urllib.error.URLError as e:
        print(f"Health check failed: {e}")
        return False
    except Exception as e:
        print(f"Health check failed with unexpected error: {e}")
        return False

if __name__ == "__main__":
    if health_check():
        sys.exit(0)
    else:
        sys.exit(1)