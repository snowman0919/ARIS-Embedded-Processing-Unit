#!/usr/bin/env python3
"""Validate the V2 LiDAR rosbag acceptance contract.

The validator intentionally checks metadata first: it is fast, works before
replay, and gives operators a clear pass/fail gate for real bags before they are
used as localization evidence.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import yaml


DEFAULT_TOPIC_CONTRACT = {
    "/cmd_drive": ("ackermann_msgs/msg/AckermannDriveStamped", 10),
    "/scan_cloud": ("sensor_msgs/msg/PointCloud2", 10),
    "/gazebo/odom": ("nav_msgs/msg/Odometry", 10),
    "/odometry/filtered": ("nav_msgs/msg/Odometry", 10),
    "/tf": ("tf2_msgs/msg/TFMessage", 1),
}


def _metadata_path(path: Path) -> Path:
    if path.is_file() and path.name == "metadata.yaml":
        return path
    return path / "metadata.yaml"


def _load_metadata(path: Path) -> dict[str, Any]:
    metadata_path = _metadata_path(path)
    if not metadata_path.exists():
        raise ValueError(f"missing rosbag metadata: {metadata_path}")
    with metadata_path.open("r") as handle:
        metadata = yaml.safe_load(handle)
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata is not a YAML mapping: {metadata_path}")
    info = metadata.get("rosbag2_bagfile_information")
    if not isinstance(info, dict):
        raise ValueError(f"missing rosbag2_bagfile_information in {metadata_path}")
    return info


def _topics(info: dict[str, Any]) -> dict[str, tuple[str, int]]:
    topics: dict[str, tuple[str, int]] = {}
    for item in info.get("topics_with_message_count", []):
        topic_metadata = item.get("topic_metadata", {})
        name = topic_metadata.get("name")
        msg_type = topic_metadata.get("type", "")
        if name:
            topics[str(name)] = (str(msg_type), int(item.get("message_count", 0)))
    return topics


def validate_bag(
    bag_path: Path,
    *,
    storage: str,
    min_duration_s: float,
    topic_contract: dict[str, tuple[str, int]],
) -> tuple[dict[str, Any], dict[str, tuple[str, int]]]:
    info = _load_metadata(bag_path)
    topics = _topics(info)
    failures: list[str] = []

    actual_storage = str(info.get("storage_identifier", ""))
    if storage and actual_storage != storage:
        failures.append(f"storage_identifier={actual_storage!r}, expected {storage}")

    duration_ns = int(info.get("duration", {}).get("nanoseconds", 0))
    if duration_ns < int(min_duration_s * 1e9):
        failures.append(f"duration_s={duration_ns / 1e9:.3f}, expected >= {min_duration_s:.3f}")

    for topic, (expected_type, minimum_count) in topic_contract.items():
        actual_type, actual_count = topics.get(topic, ("", 0))
        if actual_count < minimum_count:
            failures.append(f"{topic} count={actual_count}, expected >= {minimum_count}")
        if expected_type and actual_type and actual_type != expected_type:
            failures.append(f"{topic} type={actual_type!r}, expected {expected_type}")
        if expected_type and not actual_type:
            failures.append(f"{topic} type missing, expected {expected_type}")

    message_count = int(info.get("message_count", 0))
    if message_count < sum(minimum for _, minimum in topic_contract.values()):
        failures.append(f"message_count={message_count}, too low for required topics")

    if failures:
        raise ValueError("; ".join(failures))
    return info, topics


def _parse_topic_min(value: str) -> tuple[str, int]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected TOPIC=COUNT")
    topic, count_text = value.split("=", 1)
    try:
        count = int(count_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid count in {value!r}") from exc
    return topic, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path, help="Bag directory or metadata.yaml path")
    parser.add_argument("--storage", default="mcap", help="Expected rosbag storage identifier")
    parser.add_argument("--min-duration-s", type=float, default=3.0)
    parser.add_argument(
        "--min-topic",
        action="append",
        default=[],
        type=_parse_topic_min,
        metavar="TOPIC=COUNT",
        help="Override/add a minimum count while preserving expected type if known",
    )
    args = parser.parse_args(argv)

    contract = dict(DEFAULT_TOPIC_CONTRACT)
    for topic, count in args.min_topic:
        expected_type = contract.get(topic, ("", 0))[0]
        contract[topic] = (expected_type, count)

    try:
        info, topics = validate_bag(
            args.bag,
            storage=args.storage,
            min_duration_s=args.min_duration_s,
            topic_contract=contract,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    duration_s = int(info.get("duration", {}).get("nanoseconds", 0)) / 1e9
    counts = {topic: topics.get(topic, ("", 0))[1] for topic in sorted(contract)}
    print(
        "v2_lidar_bag_valid path={} duration_s={:.3f} messages={} counts={}".format(
            args.bag,
            duration_s,
            int(info.get("message_count", 0)),
            counts,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
