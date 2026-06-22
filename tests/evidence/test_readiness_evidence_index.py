import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_readiness_evidence_index import generate_index


def test_readiness_evidence_index_collects_latest_artifacts(tmp_path):
    logs = tmp_path / "logs"
    readiness = logs / "readiness"
    bags = logs / "bags" / "bag1"
    maps = logs / "maps"
    readiness.mkdir(parents=True)
    bags.mkdir(parents=True)
    maps.mkdir(parents=True)

    (readiness / "core_readiness_20260101T000000Z.log").write_text(
        "timestamp_utc=20260101T000000Z\n"
        "git_branch=v3\n"
        "git_commit=abc1234\n"
        "skip_v3=0\n"
        "skip_gazebo=1\n"
        "real_actuation=0\n"
        "result=PASS\n"
        "exit_code=0\n",
        encoding="utf-8",
    )
    (bags / "metadata.yaml").write_text(
        "rosbag2_bagfile_information:\n"
        "  storage_identifier: mcap\n"
        "  duration:\n"
        "    nanoseconds: 5000000000\n"
        "  message_count: 12\n"
        "  topics_with_message_count:\n"
        "    - topic_metadata:\n"
        "        name: /scan_cloud\n"
        "        type: sensor_msgs/msg/PointCloud2\n"
        "      message_count: 12\n",
        encoding="utf-8",
    )
    manifest = {
        "artifact_type": "aris_semantic_map_snapshot_manifest",
        "valid": True,
        "snapshot_sha256": "abc",
    }
    compare = {
        "artifact_type": "aris_semantic_map_repeat_pass_compare",
        "valid": True,
        "metric_overlap_ratio": 1.0,
    }
    (maps / "v3_semantic_map_20260101.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (maps / "v3_semantic_map_20260101.compare.json").write_text(json.dumps(compare), encoding="utf-8")

    index = generate_index(tmp_path / "workspace", logs)

    assert index["readiness"]["result"] == "PASS"
    assert index["git"] == {"branch": "v3", "commit": "abc1234"}
    assert index["v2_lidar_bag"]["topics"]["/scan_cloud"]["count"] == 12
    assert index["v3_semantic_map"]["manifest"]["valid"]
    assert index["v3_semantic_map"]["compare"]["metric_overlap_ratio"] == 1.0
