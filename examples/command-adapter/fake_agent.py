from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    observations = []
    for decision in packet["decisions"]:
        if decision["verdict"] == "allow":
            event_type = "action_executed"
        elif decision["verdict"] == "ask":
            event_type = "approval_requested"
        else:
            event_type = "action_blocked"
        observations.append({"event_type": event_type, "action_id": decision["action_id"]})
    observations.append(
        {
            "event_type": "artifact",
            "path": "command-result.json",
            "content": {
                "case_id": packet["case"]["id"],
                "synthetic": True,
                "status": "completed",
            },
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"observations": observations}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
