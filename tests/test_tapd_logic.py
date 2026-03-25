import os
import sys

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from test_platform.infrastructure.tapd_client import TAPDClient

def test_mappings():
    print("Testing priority mapping...")
    assert TAPDClient.map_priority("P0 (紧急)") == "urgent"
    assert TAPDClient.map_priority("P3 (低)") == "low"
    assert TAPDClient.map_priority("未知") == "medium"
    print("Priority mapping: PASSED")

    print("Testing severity mapping...")
    assert TAPDClient.map_severity("致命") == "fatal"
    assert TAPDClient.map_severity("轻微") == "slight"
    assert TAPDClient.map_severity("未知") == "normal"
    print("Severity mapping: PASSED")

if __name__ == "__main__":
    try:
        test_mappings()
        print("\nAll logic tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
