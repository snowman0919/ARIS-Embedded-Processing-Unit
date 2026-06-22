import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  runApp(const ArisGuiApp());
}

class ArisGuiApp extends StatelessWidget {
  const ArisGuiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'ARIS Operator Console',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff247c6a),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xffedf1ec),
        fontFamily: 'Roboto',
      ),
      home: const OperatorConsoleScreen(),
    );
  }
}

enum ConsoleMode { standby, manual, autonomous }

enum MapLayer { semantic, route, lidar }

enum ReviewDecision { pending, approved, rejected }

class GoalTarget {
  const GoalTarget({
    required this.name,
    required this.x,
    required this.y,
    required this.risk,
    required this.eta,
    required this.distanceM,
  });

  final String name;
  final double x;
  final double y;
  final String risk;
  final String eta;
  final int distanceM;
}

class MapChange {
  const MapChange({
    required this.id,
    required this.label,
    required this.position,
    required this.risk,
    required this.confidence,
  });

  final String id;
  final String label;
  final String position;
  final String risk;
  final int confidence;
}

class ConsoleEvent {
  const ConsoleEvent(this.time, this.text, this.tone);

  final String time;
  final String text;
  final Color tone;
}

class MapPoint {
  const MapPoint({required this.x, required this.y});

  final double x;
  final double y;

  factory MapPoint.fromJson(Map<String, Object?> json) {
    return MapPoint(
      x: (json['x'] as num).toDouble(),
      y: (json['y'] as num).toDouble(),
    );
  }
}

class SemanticMapCell {
  const SemanticMapCell({
    required this.x,
    required this.y,
    required this.label,
    required this.confidence,
    required this.traversability,
  });

  final double x;
  final double y;
  final String label;
  final double confidence;
  final double traversability;

  factory SemanticMapCell.fromJson(Map<String, Object?> json) {
    return SemanticMapCell(
      x: (json['x'] as num).toDouble(),
      y: (json['y'] as num).toDouble(),
      label: json['label'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      traversability: (json['traversability'] as num).toDouble(),
    );
  }
}

class LidarReturn {
  const LidarReturn({
    required this.x,
    required this.y,
    required this.intensity,
  });

  final double x;
  final double y;
  final double intensity;

  factory LidarReturn.fromJson(Map<String, Object?> json) {
    return LidarReturn(
      x: (json['x'] as num).toDouble(),
      y: (json['y'] as num).toDouble(),
      intensity: (json['intensity'] as num).toDouble(),
    );
  }
}

class MapSnapshot {
  const MapSnapshot({
    required this.mapId,
    required this.frame,
    required this.boundsMinX,
    required this.boundsMaxX,
    required this.boundsMinY,
    required this.boundsMaxY,
    required this.vehiclePose,
    required this.goal,
    required this.globalPath,
    required this.localPath,
    required this.semanticCells,
    required this.lidarReturns,
  });

  final String mapId;
  final String frame;
  final double boundsMinX;
  final double boundsMaxX;
  final double boundsMinY;
  final double boundsMaxY;
  final MapPoint vehiclePose;
  final MapPoint goal;
  final List<MapPoint> globalPath;
  final List<MapPoint> localPath;
  final List<SemanticMapCell> semanticCells;
  final List<LidarReturn> lidarReturns;

  factory MapSnapshot.fromJson(Map<String, Object?> json) {
    List<T> listOf<T>(
      String key,
      T Function(Map<String, Object?> item) decode,
    ) {
      return (json[key] as List<Object?>? ?? [])
          .whereType<Map>()
          .map((item) => item.cast<String, Object?>())
          .map(decode)
          .toList(growable: false);
    }

    final bounds =
        (json['bounds'] as Map?)?.cast<String, Object?>() ??
        <String, Object?>{};
    return MapSnapshot(
      mapId: json['map_id'] as String? ?? 'unknown-map',
      frame: json['frame'] as String? ?? 'map',
      boundsMinX: (bounds['min_x'] as num? ?? 0).toDouble(),
      boundsMaxX: (bounds['max_x'] as num? ?? 24).toDouble(),
      boundsMinY: (bounds['min_y'] as num? ?? -3).toDouble(),
      boundsMaxY: (bounds['max_y'] as num? ?? 3).toDouble(),
      vehiclePose: MapPoint.fromJson(
        (json['vehicle_pose'] as Map?)?.cast<String, Object?>() ??
            {'x': 0.0, 'y': 0.0},
      ),
      goal: MapPoint.fromJson(
        (json['goal'] as Map?)?.cast<String, Object?>() ?? {'x': 9.0, 'y': 0.0},
      ),
      globalPath: listOf('global_path', MapPoint.fromJson),
      localPath: listOf('local_path', MapPoint.fromJson),
      semanticCells: listOf('semantic_cells', SemanticMapCell.fromJson),
      lidarReturns: listOf('lidar_returns', LidarReturn.fromJson),
    );
  }

  factory MapSnapshot.demo() {
    const route = [
      MapPoint(x: 0.0, y: 0.0),
      MapPoint(x: 3.0, y: 0.0),
      MapPoint(x: 6.0, y: 1.2),
      MapPoint(x: 9.0, y: 1.2),
      MapPoint(x: 11.0, y: 0.0),
    ];
    return const MapSnapshot(
      mapId: 'fallback-demo',
      frame: 'map',
      boundsMinX: -1.0,
      boundsMaxX: 12.0,
      boundsMinY: -2.5,
      boundsMaxY: 2.5,
      vehiclePose: MapPoint(x: 4.8, y: 0.7),
      goal: MapPoint(x: 11.0, y: 0.0),
      globalPath: route,
      localPath: route,
      semanticCells: [
        SemanticMapCell(
          x: 6.0,
          y: 0.0,
          label: 'debris',
          confidence: 0.88,
          traversability: 1.0,
        ),
        SemanticMapCell(
          x: 2.5,
          y: -1.1,
          label: 'grass',
          confidence: 0.74,
          traversability: 0.35,
        ),
      ],
      lidarReturns: [
        LidarReturn(x: 7.8, y: 0.8, intensity: 130.0),
        LidarReturn(x: 10.0, y: -2.2, intensity: 95.0),
      ],
    );
  }

  Offset toCanvas(MapPoint point, Size size) {
    final width = math.max(0.001, boundsMaxX - boundsMinX);
    final height = math.max(0.001, boundsMaxY - boundsMinY);
    final normalizedX = ((point.x - boundsMinX) / width).clamp(0.0, 1.0);
    final normalizedY = ((point.y - boundsMinY) / height).clamp(0.0, 1.0);
    return Offset(normalizedX * size.width, (1.0 - normalizedY) * size.height);
  }
}

const demoGoals = [
  GoalTarget(
    name: 'Lab Gate',
    x: 0.78,
    y: 0.23,
    risk: 'low',
    eta: '02:18',
    distanceM: 84,
  ),
  GoalTarget(
    name: 'North Loop',
    x: 0.52,
    y: 0.18,
    risk: 'medium',
    eta: '03:42',
    distanceM: 126,
  ),
  GoalTarget(
    name: 'Parking Bay',
    x: 0.68,
    y: 0.72,
    risk: 'low',
    eta: '04:05',
    distanceM: 148,
  ),
];

const demoChanges = [
  MapChange(
    id: 'chg-118',
    label: 'new debris near route edge',
    position: 'x 6.0, y 0.0',
    risk: 'high',
    confidence: 88,
  ),
  MapChange(
    id: 'chg-119',
    label: 'grass boundary drift',
    position: 'x 4.5, y 1.1',
    risk: 'medium',
    confidence: 74,
  ),
  MapChange(
    id: 'chg-120',
    label: 'lane marking confirmed',
    position: 'x 7.4, y 0.8',
    risk: 'low',
    confidence: 93,
  ),
];

class OperatorConsoleScreen extends StatefulWidget {
  const OperatorConsoleScreen({super.key});

  @override
  State<OperatorConsoleScreen> createState() => _OperatorConsoleScreenState();
}

class _OperatorConsoleScreenState extends State<OperatorConsoleScreen> {
  ConsoleMode mode = ConsoleMode.autonomous;
  MapLayer layer = MapLayer.semantic;
  GoalTarget selectedGoal = demoGoals.first;
  MapSnapshot mapSnapshot = MapSnapshot.demo();
  bool mapSnapshotLoaded = false;
  bool dryRun = true;
  bool estopLatched = false;
  bool missionActive = true;
  double routeProgress = 0.36;
  double steeringRad = 0.18;
  final Map<String, ReviewDecision> reviewState = {
    for (final change in demoChanges) change.id: ReviewDecision.pending,
  };
  final List<ConsoleEvent> events = [
    const ConsoleEvent('09:21:18', '/scan_cloud healthy', Color(0xff247c6a)),
    const ConsoleEvent(
      '09:21:20',
      'semantic detour selected',
      Color(0xff4d6896),
    ),
    const ConsoleEvent(
      '09:21:24',
      'review required: debris',
      Color(0xffb42318),
    ),
  ];
  Timer? ticker;

  @override
  void initState() {
    super.initState();
    _loadMapSnapshot();
    ticker = Timer.periodic(const Duration(milliseconds: 600), (_) {
      if (!mounted ||
          estopLatched ||
          !missionActive ||
          mode != ConsoleMode.autonomous) {
        return;
      }
      setState(() {
        routeProgress = (routeProgress + 0.006).clamp(0.0, 1.0);
        steeringRad = 0.16 + math.sin(routeProgress * math.pi * 2.0) * 0.08;
      });
    });
  }

  Future<void> _loadMapSnapshot() async {
    try {
      final raw = await rootBundle.loadString(
        'assets/snapshots/aris_map_snapshot.json',
      );
      final decoded = jsonDecode(raw) as Map<String, Object?>;
      if (!mounted) {
        return;
      }
      setState(() {
        mapSnapshot = MapSnapshot.fromJson(decoded);
        mapSnapshotLoaded = true;
        events.insert(
          0,
          ConsoleEvent(
            'now',
            'loaded map snapshot: ${mapSnapshot.mapId}',
            const Color(0xff247c6a),
          ),
        );
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        mapSnapshotLoaded = false;
        events.insert(
          0,
          ConsoleEvent(
            'now',
            'map snapshot fallback: $error',
            const Color(0xffa3560b),
          ),
        );
      });
    }
  }

  @override
  void dispose() {
    ticker?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: AspectRatio(
            aspectRatio: 16 / 10,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1280, maxHeight: 800),
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  children: [
                    _HeaderBar(
                      mode: mode,
                      dryRun: dryRun,
                      estopLatched: estopLatched,
                      onModeChanged: (value) => setState(() => mode = value),
                      onDryRunChanged: (value) =>
                          setState(() => dryRun = value),
                      onEstopPressed: _latchEstop,
                    ),
                    const SizedBox(height: 8),
                    _TelemetryStrip(
                      progress: routeProgress,
                      goal: selectedGoal,
                      estopLatched: estopLatched,
                      missionActive: missionActive,
                      dryRun: dryRun,
                      steeringRad: steeringRad,
                    ),
                    const SizedBox(height: 8),
                    Expanded(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Expanded(
                            flex: 7,
                            child: _MapPanel(
                              layer: layer,
                              goal: selectedGoal,
                              snapshot: mapSnapshot,
                              snapshotLoaded: mapSnapshotLoaded,
                              progress: routeProgress,
                              estopLatched: estopLatched,
                              onLayerChanged: (value) =>
                                  setState(() => layer = value),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            flex: 5,
                            child: Column(
                              children: [
                                Expanded(
                                  flex: 5,
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: _MissionPanel(
                                          goals: demoGoals,
                                          selectedGoal: selectedGoal,
                                          missionActive: missionActive,
                                          progress: routeProgress,
                                          onGoalChanged: (goal) => setState(() {
                                            selectedGoal = goal;
                                            routeProgress = 0.0;
                                            missionActive = true;
                                          }),
                                          onToggleMission: () => setState(
                                            () =>
                                                missionActive = !missionActive,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: _SafetyPanel(
                                          estopLatched: estopLatched,
                                          dryRun: dryRun,
                                          onEstopPressed: _latchEstop,
                                          onClearPressed: _clearEstop,
                                          onDryRunChanged: (value) =>
                                              setState(() => dryRun = value),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Expanded(
                                  flex: 4,
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: _VehiclePanel(
                                          estopLatched: estopLatched,
                                          dryRun: dryRun,
                                          progress: routeProgress,
                                          steeringRad: steeringRad,
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: _ReviewPanel(
                                          state: reviewState,
                                          onDecision: _setReviewDecision,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    _EventRail(events: events),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _latchEstop() {
    setState(() {
      estopLatched = true;
      missionActive = false;
      events.insert(
        0,
        const ConsoleEvent(
          'now',
          'E-stop latched: safe stop',
          Color(0xffb42318),
        ),
      );
    });
  }

  void _clearEstop() {
    setState(() {
      estopLatched = false;
      events.insert(
        0,
        const ConsoleEvent('now', 'operator cleared E-stop', Color(0xff247c6a)),
      );
    });
  }

  void _setReviewDecision(String id, ReviewDecision decision) {
    setState(() {
      reviewState[id] = decision;
      final verb = decision == ReviewDecision.approved
          ? 'approved'
          : 'rejected';
      events.insert(
        0,
        ConsoleEvent('now', 'map change $id $verb', _decisionColor(decision)),
      );
    });
  }
}

class _HeaderBar extends StatelessWidget {
  const _HeaderBar({
    required this.mode,
    required this.dryRun,
    required this.estopLatched,
    required this.onModeChanged,
    required this.onDryRunChanged,
    required this.onEstopPressed,
  });

  final ConsoleMode mode;
  final bool dryRun;
  final bool estopLatched;
  final ValueChanged<ConsoleMode> onModeChanged;
  final ValueChanged<bool> onDryRunChanged;
  final VoidCallback onEstopPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: Row(
        children: [
          const SizedBox(
            width: 232,
            child: Row(
              children: [
                Icon(Icons.trip_origin, size: 30, color: Color(0xff247c6a)),
                SizedBox(width: 8),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'ARIS Console',
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        '8.8 in 16:10 control',
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 11,
                          color: Color(0xff66706a),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          SegmentedButton<ConsoleMode>(
            showSelectedIcon: false,
            style: const ButtonStyle(
              visualDensity: VisualDensity(horizontal: -2, vertical: -2),
            ),
            segments: const [
              ButtonSegment(
                value: ConsoleMode.standby,
                icon: Icon(Icons.pause),
                label: Text('Standby'),
              ),
              ButtonSegment(
                value: ConsoleMode.manual,
                icon: Icon(Icons.gamepad),
                label: Text('Manual'),
              ),
              ButtonSegment(
                value: ConsoleMode.autonomous,
                icon: Icon(Icons.route),
                label: Text('Auto'),
              ),
            ],
            selected: {mode},
            onSelectionChanged: (values) => onModeChanged(values.first),
          ),
          const Spacer(),
          _StatusPill(
            icon: Icons.sensors,
            label: 'V2A',
            tone: const Color(0xff247c6a),
          ),
          const SizedBox(width: 6),
          _StatusPill(
            icon: dryRun ? Icons.shield_outlined : Icons.warning_amber,
            label: dryRun ? 'dry-run' : 'armed',
            tone: dryRun ? const Color(0xff247c6a) : const Color(0xffa3560b),
          ),
          const SizedBox(width: 6),
          Switch(value: dryRun, onChanged: onDryRunChanged),
          const SizedBox(width: 6),
          FilledButton.icon(
            style: FilledButton.styleFrom(
              backgroundColor: estopLatched
                  ? const Color(0xff7f1d1d)
                  : const Color(0xffb42318),
              fixedSize: const Size(118, 44),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            onPressed: onEstopPressed,
            icon: const Icon(Icons.emergency_share, size: 18),
            label: const Text('E-stop'),
          ),
        ],
      ),
    );
  }
}

class _TelemetryStrip extends StatelessWidget {
  const _TelemetryStrip({
    required this.progress,
    required this.goal,
    required this.estopLatched,
    required this.missionActive,
    required this.dryRun,
    required this.steeringRad,
  });

  final double progress;
  final GoalTarget goal;
  final bool estopLatched;
  final bool missionActive;
  final bool dryRun;
  final double steeringRad;

  @override
  Widget build(BuildContext context) {
    final speed = estopLatched || !missionActive ? 0.0 : 1.4;
    return SizedBox(
      height: 50,
      child: Row(
        children: [
          Expanded(
            child: _TelemetryTile(
              icon: Icons.flag_outlined,
              label: 'goal',
              value: goal.name,
              tone: const Color(0xff247c6a),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _TelemetryTile(
              icon: Icons.timeline,
              label: 'route',
              value: '${(progress * 100).round()}%',
              tone: const Color(0xff4d6896),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _TelemetryTile(
              icon: Icons.speed,
              label: 'speed',
              value: '${speed.toStringAsFixed(1)} m/s',
              tone: const Color(0xff247c6a),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _TelemetryTile(
              icon: Icons.rotate_right,
              label: 'steer',
              value: '${steeringRad.toStringAsFixed(2)} rad',
              tone: const Color(0xff4d6896),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _TelemetryTile(
              icon: estopLatched ? Icons.block : Icons.favorite_border,
              label: 'safety',
              value: estopLatched
                  ? 'safe stop'
                  : dryRun
                  ? 'sim gate'
                  : 'armed',
              tone: estopLatched
                  ? const Color(0xffb42318)
                  : const Color(0xff247c6a),
            ),
          ),
        ],
      ),
    );
  }
}

class _MapPanel extends StatelessWidget {
  const _MapPanel({
    required this.layer,
    required this.goal,
    required this.snapshot,
    required this.snapshotLoaded,
    required this.progress,
    required this.estopLatched,
    required this.onLayerChanged,
  });

  final MapLayer layer;
  final GoalTarget goal;
  final MapSnapshot snapshot;
  final bool snapshotLoaded;
  final double progress;
  final bool estopLatched;
  final ValueChanged<MapLayer> onLayerChanged;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Map Viewer',
      icon: Icons.map_outlined,
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: MapLayer.values.map((value) {
          return Padding(
            padding: const EdgeInsets.only(left: 4),
            child: ChoiceChip(
              visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
              label: Text(_layerLabel(value)),
              selected: layer == value,
              onSelected: (_) => onLayerChanged(value),
            ),
          );
        }).toList(),
      ),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: CustomPaint(
            painter: _MapPainter(
              layer: layer,
              goal: goal,
              snapshot: snapshot,
              progress: progress,
              estopLatched: estopLatched,
            ),
            child: Stack(
              children: [
                Positioned(
                  left: 10,
                  top: 10,
                  child: _MapOverlay(
                    goal: goal,
                    snapshot: snapshot,
                    snapshotLoaded: snapshotLoaded,
                    progress: progress,
                  ),
                ),
                const Positioned(right: 10, bottom: 10, child: _MapScale()),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MissionPanel extends StatelessWidget {
  const _MissionPanel({
    required this.goals,
    required this.selectedGoal,
    required this.missionActive,
    required this.progress,
    required this.onGoalChanged,
    required this.onToggleMission,
  });

  final List<GoalTarget> goals;
  final GoalTarget selectedGoal;
  final bool missionActive;
  final double progress;
  final ValueChanged<GoalTarget> onGoalChanged;
  final VoidCallback onToggleMission;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Mission',
      icon: Icons.flag_outlined,
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          children: [
            Expanded(
              child: ListView.separated(
                itemCount: goals.length,
                separatorBuilder: (_, _) => const SizedBox(height: 6),
                itemBuilder: (context, index) {
                  final goal = goals[index];
                  final selected = goal == selectedGoal;
                  return _GoalRow(
                    goal: goal,
                    selected: selected,
                    onTap: () => onGoalChanged(goal),
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(5),
              child: LinearProgressIndicator(
                minHeight: 8,
                value: progress,
                backgroundColor: const Color(0xffd8dfd9),
                color: const Color(0xff247c6a),
              ),
            ),
            const SizedBox(height: 8),
            FilledButton.icon(
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(42),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              onPressed: onToggleMission,
              icon: Icon(missionActive ? Icons.pause : Icons.play_arrow),
              label: Text(missionActive ? 'Hold route' : 'Resume route'),
            ),
          ],
        ),
      ),
    );
  }
}

class _SafetyPanel extends StatelessWidget {
  const _SafetyPanel({
    required this.estopLatched,
    required this.dryRun,
    required this.onEstopPressed,
    required this.onClearPressed,
    required this.onDryRunChanged,
  });

  final bool estopLatched;
  final bool dryRun;
  final VoidCallback onEstopPressed;
  final VoidCallback onClearPressed;
  final ValueChanged<bool> onDryRunChanged;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Safety',
      icon: Icons.health_and_safety_outlined,
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          children: [
            _StateRow(
              icon: Icons.emergency_share,
              label: 'E-stop',
              value: estopLatched ? 'latched' : 'clear',
              tone: estopLatched
                  ? const Color(0xffb42318)
                  : const Color(0xff247c6a),
            ),
            const SizedBox(height: 6),
            _StateRow(
              icon: Icons.shield_outlined,
              label: 'gate',
              value: dryRun ? 'dry-run' : 'armed',
              tone: dryRun ? const Color(0xff247c6a) : const Color(0xffa3560b),
            ),
            const SizedBox(height: 4),
            SizedBox(
              height: 38,
              child: Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Dry-run',
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                  Switch(value: dryRun, onChanged: onDryRunChanged),
                ],
              ),
            ),
            const Spacer(),
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xffb42318),
                      minimumSize: const Size.fromHeight(42),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    onPressed: onEstopPressed,
                    child: const Text('Latch'),
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(42),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    onPressed: onClearPressed,
                    child: const Text('Clear'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _VehiclePanel extends StatelessWidget {
  const _VehiclePanel({
    required this.estopLatched,
    required this.dryRun,
    required this.progress,
    required this.steeringRad,
  });

  final bool estopLatched;
  final bool dryRun;
  final double progress;
  final double steeringRad;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Vehicle',
      icon: Icons.monitor_heart_outlined,
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          children: [
            Expanded(
              child: Row(
                children: [
                  Expanded(
                    child: _MetricTile(
                      icon: Icons.speed,
                      label: 'speed',
                      value: estopLatched ? '0.0' : '1.4',
                      unit: 'm/s',
                      tone: const Color(0xff247c6a),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: _MetricTile(
                      icon: Icons.rotate_right,
                      label: 'steer',
                      value: steeringRad.toStringAsFixed(2),
                      unit: 'rad',
                      tone: const Color(0xff4d6896),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 6),
            Expanded(
              child: Row(
                children: [
                  Expanded(
                    child: _MetricTile(
                      icon: Icons.location_searching,
                      label: 'loc',
                      value: '${(98 - progress * 6).round()}',
                      unit: '%',
                      tone: const Color(0xff247c6a),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: _MetricTile(
                      icon: Icons.battery_5_bar,
                      label: 'battery',
                      value: dryRun ? 'sim' : '48.2',
                      unit: dryRun ? '' : 'V',
                      tone: const Color(0xff8a6a16),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReviewPanel extends StatelessWidget {
  const _ReviewPanel({required this.state, required this.onDecision});

  final Map<String, ReviewDecision> state;
  final void Function(String id, ReviewDecision decision) onDecision;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Review',
      icon: Icons.rate_review_outlined,
      child: ListView.separated(
        padding: const EdgeInsets.all(8),
        itemCount: demoChanges.length,
        separatorBuilder: (_, _) => const SizedBox(height: 6),
        itemBuilder: (context, index) {
          final change = demoChanges[index];
          final decision = state[change.id] ?? ReviewDecision.pending;
          return _ReviewRow(
            change: change,
            decision: decision,
            onApprove: () => onDecision(change.id, ReviewDecision.approved),
            onReject: () => onDecision(change.id, ReviewDecision.rejected),
          );
        },
      ),
    );
  }
}

class _EventRail extends StatelessWidget {
  const _EventRail({required this.events});

  final List<ConsoleEvent> events;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 58,
      decoration: BoxDecoration(
        color: const Color(0xfffbfcfa),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd5ddd7)),
      ),
      child: Row(
        children: [
          const SizedBox(width: 10),
          const Icon(
            Icons.receipt_long_outlined,
            size: 18,
            color: Color(0xff247c6a),
          ),
          const SizedBox(width: 7),
          const SizedBox(
            width: 76,
            child: Text(
              'Event Log',
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              itemCount: math.min(events.length, 6),
              separatorBuilder: (_, _) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                final event = events[index];
                return Container(
                  width: 250,
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  decoration: BoxDecoration(
                    color: event.tone.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: event.tone.withValues(alpha: 0.22),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.circle, size: 9, color: event.tone),
                      const SizedBox(width: 8),
                      Text(
                        event.time,
                        style: const TextStyle(
                          fontSize: 11,
                          color: Color(0xff66706a),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          event.text,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _GoalRow extends StatelessWidget {
  const _GoalRow({
    required this.goal,
    required this.selected,
    required this.onTap,
  });

  final GoalTarget goal;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: onTap,
      child: Container(
        height: 54,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          color: selected ? const Color(0xffe1f1eb) : Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: selected ? const Color(0xff247c6a) : const Color(0xffd5ddd7),
          ),
        ),
        child: Row(
          children: [
            Icon(
              selected
                  ? Icons.radio_button_checked
                  : Icons.radio_button_unchecked,
              size: 20,
              color: selected
                  ? const Color(0xff247c6a)
                  : const Color(0xff78837e),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    goal.name,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  Text(
                    '${goal.distanceM} m  eta ${goal.eta}',
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xff66706a),
                    ),
                  ),
                ],
              ),
            ),
            _RiskDot(risk: goal.risk),
          ],
        ),
      ),
    );
  }
}

class _ReviewRow extends StatelessWidget {
  const _ReviewRow({
    required this.change,
    required this.decision,
    required this.onApprove,
    required this.onReject,
  });

  final MapChange change;
  final ReviewDecision decision;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final done = decision != ReviewDecision.pending;
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: done
            ? _decisionColor(decision).withValues(alpha: 0.08)
            : Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd5ddd7)),
      ),
      child: Row(
        children: [
          Icon(
            done ? _decisionIcon(decision) : Icons.pending_actions,
            color: done ? _decisionColor(decision) : _riskColor(change.risk),
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  change.label,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                Text(
                  '${change.position}  ${change.confidence}%',
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 11,
                    color: Color(0xff66706a),
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
            tooltip: 'Approve',
            onPressed: done ? null : onApprove,
            icon: const Icon(Icons.done),
          ),
          IconButton(
            visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
            tooltip: 'Reject',
            onPressed: done ? null : onReject,
            icon: const Icon(Icons.close),
          ),
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({
    required this.title,
    required this.icon,
    required this.child,
    this.trailing,
  });

  final String title;
  final IconData icon;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xfffbfcfa),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd5ddd7)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x10000000),
            blurRadius: 8,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          SizedBox(
            height: 40,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              child: Row(
                children: [
                  Icon(icon, size: 18, color: const Color(0xff247c6a)),
                  const SizedBox(width: 7),
                  Expanded(
                    child: Text(
                      title,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  ?trailing,
                ],
              ),
            ),
          ),
          const Divider(height: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _TelemetryTile extends StatelessWidget {
  const _TelemetryTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd5ddd7)),
      ),
      child: Row(
        children: [
          Icon(icon, size: 19, color: tone),
          const SizedBox(width: 8),
          Text(
            label,
            style: const TextStyle(fontSize: 11, color: Color(0xff66706a)),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              value,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.unit,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final String value;
  final String unit;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: tone.withValues(alpha: 0.18)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: tone, size: 18),
          const SizedBox(height: 5),
          Text(
            label,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 11, color: Color(0xff66706a)),
          ),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              unit.isEmpty ? value : '$value $unit',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _StateRow extends StatelessWidget {
  const _StateRow({
    required this.icon,
    required this.label,
    required this.value,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 42,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: tone.withValues(alpha: 0.18)),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: tone),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          Text(
            value,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: tone, fontWeight: FontWeight.w900),
          ),
        ],
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({
    required this.icon,
    required this.label,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 30,
      padding: const EdgeInsets.symmetric(horizontal: 9),
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: tone.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: tone),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: tone,
              fontSize: 12,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskDot extends StatelessWidget {
  const _RiskDot({required this.risk});

  final String risk;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(
        color: _riskColor(risk),
        shape: BoxShape.circle,
      ),
    );
  }
}

class _MapOverlay extends StatelessWidget {
  const _MapOverlay({
    required this.goal,
    required this.snapshot,
    required this.snapshotLoaded,
    required this.progress,
  });

  final GoalTarget goal;
  final MapSnapshot snapshot;
  final bool snapshotLoaded;
  final double progress;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 190,
      padding: const EdgeInsets.all(9),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd5ddd7)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Goal: ${goal.name}',
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w900),
          ),
          Text(
            snapshotLoaded ? snapshot.mapId : 'fallback map',
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 10, color: Color(0xff5f6f65)),
          ),
          const SizedBox(height: 6),
          _LegendItem(
            color: const Color(0xff247c6a),
            label:
                '${snapshot.globalPath.length} pts ${(progress * 100).round()}%',
          ),
          const _LegendItem(color: Color(0xff4d6896), label: 'local plan'),
          _LegendItem(
            color: const Color(0xffb42318),
            label: '${snapshot.semanticCells.length} semantic cells',
          ),
        ],
      ),
    );
  }
}

class _LegendItem extends StatelessWidget {
  const _LegendItem({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 18,
      child: Row(
        children: [
          Container(
            width: 9,
            height: 9,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }
}

class _MapScale extends StatelessWidget {
  const _MapScale();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 98,
      height: 30,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd5ddd7)),
      ),
      child: const Row(
        children: [
          Expanded(child: Divider(thickness: 3, color: Color(0xff1f2a24))),
          SizedBox(width: 6),
          Text('5 m', style: TextStyle(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _MapPainter extends CustomPainter {
  _MapPainter({
    required this.layer,
    required this.goal,
    required this.snapshot,
    required this.progress,
    required this.estopLatched,
  });

  final MapLayer layer;
  final GoalTarget goal;
  final MapSnapshot snapshot;
  final double progress;
  final bool estopLatched;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = const Color(0xffe7ece5),
    );
    _drawGrid(canvas, size);
    _drawMapBounds(canvas, size);
    if (layer == MapLayer.semantic) {
      _drawSemantic(canvas, size);
    } else if (layer == MapLayer.lidar) {
      _drawLidar(canvas, size);
    }
    _drawRoute(canvas, size);
    if (estopLatched) {
      canvas.drawRect(
        Offset.zero & size,
        Paint()..color = const Color(0x44b42318),
      );
    }
  }

  void _drawGrid(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = const Color(0xffcfd8d1)
      ..strokeWidth = 1;
    for (double x = 0; x <= size.width; x += size.width / 12) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
    }
    for (double y = 0; y <= size.height; y += size.height / 8) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }
  }

  void _drawMapBounds(Canvas canvas, Size size) {
    final bounds = Rect.fromLTWH(0, 0, size.width, size.height).deflate(14);
    canvas.drawRRect(
      RRect.fromRectAndRadius(bounds, const Radius.circular(8)),
      Paint()..color = const Color(0xffd8e1d8).withValues(alpha: 0.45),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(bounds, const Radius.circular(8)),
      Paint()
        ..color = const Color(0xff8aa092)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.4,
    );
  }

  void _drawSemantic(Canvas canvas, Size size) {
    for (final cell in snapshot.semanticCells) {
      final center = snapshot.toCanvas(MapPoint(x: cell.x, y: cell.y), size);
      final color = _semanticColor(cell.label, cell.traversability);
      final radius = 18 + cell.confidence.clamp(0.0, 1.0) * 12;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: center, width: radius * 2, height: radius),
          const Radius.circular(8),
        ),
        Paint()..color = color.withValues(alpha: 0.62),
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: center, width: radius * 2, height: radius),
          const Radius.circular(8),
        ),
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
    }
  }

  void _drawLidar(Canvas canvas, Size size) {
    final origin = snapshot.toCanvas(snapshot.vehiclePose, size);
    final ray = Paint()
      ..color = const Color(0xff4d6896).withValues(alpha: 0.35)
      ..strokeWidth = 1;
    final hitPaint = Paint()..color = const Color(0xff4d6896);
    for (final hit in snapshot.lidarReturns) {
      final target = snapshot.toCanvas(MapPoint(x: hit.x, y: hit.y), size);
      canvas.drawLine(origin, target, ray);
      canvas.drawCircle(
        target,
        (2.5 + hit.intensity / 80).clamp(2.5, 7.0),
        hitPaint,
      );
    }
  }

  void _drawRoute(Canvas canvas, Size size) {
    final route = snapshot.globalPath
        .map((point) => snapshot.toCanvas(point, size))
        .toList(growable: false);
    if (route.length < 2) {
      return;
    }
    final routePath = Path()..moveTo(route.first.dx, route.first.dy);
    for (final point in route.skip(1)) {
      routePath.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(
      routePath,
      Paint()
        ..color = const Color(0xff247c6a)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4
        ..strokeCap = StrokeCap.round,
    );

    final localRoute =
        (snapshot.localPath.isEmpty ? snapshot.globalPath : snapshot.localPath)
            .map((point) => snapshot.toCanvas(point, size))
            .toList(growable: false);
    final localPath = Path()..moveTo(localRoute.first.dx, localRoute.first.dy);
    for (final point in localRoute.skip(1)) {
      localPath.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(
      localPath,
      Paint()
        ..color = const Color(0xff4d6896)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3
        ..strokeCap = StrokeCap.round,
    );

    final vehicle = _interpolate(route, progress);
    _drawVehicle(canvas, vehicle);
    _drawGoal(canvas, snapshot.toCanvas(snapshot.goal, size));
  }

  Offset _interpolate(List<Offset> points, double t) {
    final segmentCount = points.length - 1;
    final scaled = (t.clamp(0.0, 1.0)) * segmentCount;
    final index = scaled.floor().clamp(0, segmentCount - 1);
    final local = scaled - index;
    return Offset.lerp(points[index], points[index + 1], local) ??
        points[index];
  }

  void _drawVehicle(Canvas canvas, Offset point) {
    canvas.drawCircle(point, 16, Paint()..color = Colors.white);
    canvas.drawCircle(point, 11, Paint()..color = const Color(0xff1f2a24));
    canvas.drawCircle(
      point.translate(4, -3),
      3,
      Paint()..color = const Color(0xfff5f7f3),
    );
  }

  void _drawGoal(Canvas canvas, Offset point) {
    canvas.drawCircle(point, 17, Paint()..color = Colors.white);
    canvas.drawCircle(point, 12, Paint()..color = const Color(0xff8a6a16));
    canvas.drawCircle(point, 5, Paint()..color = const Color(0xfff5c542));
  }

  @override
  bool shouldRepaint(covariant _MapPainter oldDelegate) {
    return oldDelegate.layer != layer ||
        oldDelegate.goal != goal ||
        oldDelegate.snapshot != snapshot ||
        oldDelegate.progress != progress ||
        oldDelegate.estopLatched != estopLatched;
  }
}

String _layerLabel(MapLayer layer) {
  switch (layer) {
    case MapLayer.semantic:
      return 'Sem';
    case MapLayer.route:
      return 'Route';
    case MapLayer.lidar:
      return 'LiDAR';
  }
}

Color _riskColor(String risk) {
  switch (risk) {
    case 'high':
      return const Color(0xffb42318);
    case 'medium':
      return const Color(0xffa66f00);
    default:
      return const Color(0xff247c6a);
  }
}

Color _semanticColor(String label, double traversability) {
  final normalizedLabel = label.toLowerCase();
  if (normalizedLabel.contains('grass') ||
      normalizedLabel.contains('low_traversability')) {
    return const Color(0xff6aa06a);
  }
  if (normalizedLabel.contains('debris') ||
      normalizedLabel.contains('obstacle') ||
      traversability >= 0.8) {
    return const Color(0xffb42318);
  }
  return const Color(0xffa66f00);
}

IconData _decisionIcon(ReviewDecision decision) {
  switch (decision) {
    case ReviewDecision.approved:
      return Icons.check_circle;
    case ReviewDecision.rejected:
      return Icons.cancel;
    case ReviewDecision.pending:
      return Icons.pending_actions;
  }
}

Color _decisionColor(ReviewDecision decision) {
  switch (decision) {
    case ReviewDecision.approved:
      return const Color(0xff247c6a);
    case ReviewDecision.rejected:
      return const Color(0xffb42318);
    case ReviewDecision.pending:
      return const Color(0xff66706a);
  }
}
