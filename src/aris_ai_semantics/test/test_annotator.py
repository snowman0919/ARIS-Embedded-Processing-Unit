from aris_ai_semantics.annotator import annotate_json


def test_ai_annotation_is_advisory_only():
    annotation = annotate_json(
        {
            "event_id": "evt-1",
            "layer": "semantic",
            "location": [1.0, 2.0],
            "description": "fallen debris blocking path",
            "confidence": 0.8,
        }
    )
    assert annotation["advisory_only"] is True
    assert annotation["control_authority"] == "none"
    assert "possible_obstruction" in annotation["labels"]
    assert annotation["review_required"] is True
