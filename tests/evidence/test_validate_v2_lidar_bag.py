import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validate_v2_lidar_bag import DEFAULT_TOPIC_CONTRACT, validate_bag


def _write_metadata(path: Path, topics: dict[str, tuple[str, int]]) -> None:
    topic_lines = []
    total = 0
    for name, (msg_type, count) in topics.items():
        total += count
        topic_lines.append(
            "    - topic_metadata:\n"
            f"        name: {name}\n"
            f"        type: {msg_type}\n"
            f"      message_count: {count}\n"
        )
    (path / "metadata.yaml").write_text(
        "rosbag2_bagfile_information:\n"
        "  storage_identifier: mcap\n"
        "  duration:\n"
        "    nanoseconds: 5000000000\n"
        f"  message_count: {total}\n"
        "  topics_with_message_count:\n"
        + "".join(topic_lines),
        encoding="utf-8",
    )


def test_v2_bag_contract_requires_full_motion_topics(tmp_path):
    _write_metadata(
        tmp_path,
        {"/scan_cloud": ("sensor_msgs/msg/PointCloud2", 12)},
    )

    with pytest.raises(ValueError, match="/cmd_drive count=0"):
        validate_bag(
            tmp_path,
            storage="mcap",
            min_duration_s=3.0,
            topic_contract=DEFAULT_TOPIC_CONTRACT,
        )


def test_scan_only_contract_accepts_sensor_obstacle_bag(tmp_path):
    _write_metadata(
        tmp_path,
        {"/scan_cloud": ("sensor_msgs/msg/PointCloud2", 12)},
    )

    info, topics = validate_bag(
        tmp_path,
        storage="mcap",
        min_duration_s=3.0,
        topic_contract={"/scan_cloud": DEFAULT_TOPIC_CONTRACT["/scan_cloud"]},
    )

    assert info["storage_identifier"] == "mcap"
    assert topics["/scan_cloud"] == ("sensor_msgs/msg/PointCloud2", 12)
