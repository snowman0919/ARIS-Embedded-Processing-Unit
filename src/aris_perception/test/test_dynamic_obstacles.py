from aris_perception.dynamic_obstacles import (
    DynamicObstacleConfig,
    PointXYZ,
    evaluate_dynamic_obstacle,
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


def test_dynamic_obstacle_detector_slows_for_corridor_points():
    decision = evaluate_dynamic_obstacle(
        [
            PointXYZ(2.5, 0.1, 0.0),
            PointXYZ(2.7, -0.1, 0.1),
            PointXYZ(2.9, 0.0, 0.2),
        ],
        config=DynamicObstacleConfig(slow_distance_m=3.0, stop_distance_m=1.0),
    )

    assert decision.action == "slow"
    assert decision.closest_distance_m == 2.5
    assert decision.point_count == 3


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
