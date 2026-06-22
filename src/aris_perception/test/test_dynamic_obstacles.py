from aris_perception.dynamic_obstacles import (
    DynamicObstacleConfig,
    DynamicObstacleTracker,
    PointXYZ,
    evaluate_dynamic_obstacle,
    obstacle_observation,
    with_track,
)


def test_dynamic_obstacle_detector_ignores_points_outside_corridor():
    decision = evaluate_dynamic_obstacle(
        [
            PointXYZ(0.5, 2.0, 0.1),
            PointXYZ(1.0, -2.0, 0.1),
            PointXYZ(1.2, 0.1, 2.5),
        ],
        config=DynamicObstacleConfig(min_points=2),
    )

    assert decision.action == "clear"
    assert decision.reason == "insufficient_points"


def test_dynamic_obstacle_detector_detours_for_corridor_points():
    decision = evaluate_dynamic_obstacle(
        [
            PointXYZ(2.5, 0.1, 0.0),
            PointXYZ(2.7, -0.1, 0.1),
            PointXYZ(2.9, 0.0, 0.2),
        ],
        config=DynamicObstacleConfig(slow_distance_m=3.0, stop_distance_m=1.0),
    )

    assert decision.action == "detour"
    assert decision.closest_distance_m == 2.5
    assert decision.point_count == 3
    assert decision.detour_lateral_m < 0.0
    assert decision.detour_forward_m == 2.5


def test_dynamic_obstacle_detector_stops_inside_stop_distance():
    decision = evaluate_dynamic_obstacle(
        [
            PointXYZ(0.8, 0.1, 0.0),
            PointXYZ(0.9, -0.1, 0.0),
            PointXYZ(1.0, 0.0, 0.0),
        ],
        config=DynamicObstacleConfig(stop_distance_m=1.0),
    )

    assert decision.action == "stop"
    assert decision.reason == "inside_stop_distance"


def test_dynamic_obstacle_detector_stops_for_fast_closing_obstacle():
    decision = evaluate_dynamic_obstacle(
        [
            PointXYZ(2.5, 0.1, 0.0),
            PointXYZ(2.7, -0.1, 0.0),
            PointXYZ(2.9, 0.0, 0.0),
        ],
        config=DynamicObstacleConfig(slow_distance_m=3.0, stop_distance_m=1.0),
        previous_closest_m=3.4,
        dt_s=0.5,
    )

    assert decision.action == "stop"
    assert decision.reason == "closing_fast"
    assert decision.closing_speed_mps > 1.2


def test_dynamic_obstacle_tracker_keeps_persistent_track_id():
    config = DynamicObstacleConfig(track_match_distance_m=1.0)
    tracker = DynamicObstacleTracker(config)
    first = obstacle_observation(
        [
            PointXYZ(3.0, 0.1, 0.0),
            PointXYZ(3.1, 0.0, 0.0),
            PointXYZ(3.2, -0.1, 0.0),
        ],
        config=config,
    )
    second = obstacle_observation(
        [
            PointXYZ(2.8, 0.1, 0.0),
            PointXYZ(2.9, 0.0, 0.0),
            PointXYZ(3.0, -0.1, 0.0),
        ],
        config=config,
    )

    first_track = tracker.update(first, timestamp_s=1.0)
    second_track = tracker.update(second, timestamp_s=1.2)

    assert first_track is not None
    assert second_track is not None
    assert second_track.track_id == first_track.track_id
    assert second_track.age == 2
    assert abs(second_track.persistence_s - 0.2) < 1e-6
    assert second_track.velocity_x_mps < 0.0


def test_dynamic_obstacle_tracker_forgets_stale_track():
    config = DynamicObstacleConfig(track_forget_after_s=0.5)
    tracker = DynamicObstacleTracker(config)
    observation = obstacle_observation(
        [
            PointXYZ(3.0, 0.1, 0.0),
            PointXYZ(3.1, 0.0, 0.0),
            PointXYZ(3.2, -0.1, 0.0),
        ],
        config=config,
    )

    first_track = tracker.update(observation, timestamp_s=1.0)
    second_track = tracker.update(observation, timestamp_s=2.0)

    assert first_track is not None
    assert second_track is not None
    assert second_track.track_id != first_track.track_id
    assert second_track.age == 1


def test_dynamic_obstacle_decision_includes_track_metadata():
    config = DynamicObstacleConfig()
    tracker = DynamicObstacleTracker(config)
    points = [
        PointXYZ(2.5, 0.1, 0.0),
        PointXYZ(2.6, 0.0, 0.0),
        PointXYZ(2.7, -0.1, 0.0),
    ]
    track = tracker.update(obstacle_observation(points, config=config), timestamp_s=1.0)
    decision = with_track(evaluate_dynamic_obstacle(points, config=config), track)

    assert decision.track_id == 1
    assert decision.track_age == 1
    assert decision.as_dict()["track_id"] == 1
