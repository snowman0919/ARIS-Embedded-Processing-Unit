# aris_gui

Flutter operator console for ARIS. The first screen is optimized for an 8.8 inch 16:10 control
display, using 1280x800 as the test viewport. It covers the required HMI surfaces from the
architecture spec:

- map viewer with semantic / route / LiDAR layer controls backed by a map snapshot asset
- mission goal selection and route hold/resume
- vehicle monitor
- safety panel
- change review with approve/reject state
- compact event log

Use the repository Nix shell so Flutter, Dart, and Linux UI build dependencies come from Nix:

```bash
cd /home/sbeen/aris/aris-dev-env
nix develop -c bash -lc 'cd src/aris_gui && ../../scripts/run_flutter.sh analyze'
nix develop -c bash -lc 'cd src/aris_gui && ../../scripts/run_flutter.sh test'
nix develop -c bash -lc 'cd src/aris_gui && ../../scripts/run_flutter.sh build web'
```

For an interactive web-server session:

```bash
cd /home/sbeen/aris/aris-dev-env
nix develop -c bash -lc 'cd src/aris_gui && ../../scripts/run_flutter.sh run -d web-server --web-hostname 0.0.0.0 --web-port 8088'
```

The map viewer reads `assets/snapshots/aris_map_snapshot.json`. Generate that file from an existing
ARIS route CSV with:

```bash
cd /home/sbeen/aris/aris-dev-env
scripts/export_gui_snapshot.py \
  --route /home/sbeen/aris/data/routes/v3_semantic_route_20260621_123035.csv \
  --out src/aris_gui/assets/snapshots/aris_map_snapshot.json \
  --map-id v3-semantic-route-20260621
```

This is still a local Flutter control surface, but the map is no longer a pure placeholder: route,
local plan, semantic cells, and LiDAR returns are loaded from the same snapshot contract that a
future ROS2/bridge data source can publish. The GUI should keep actuation authority behind the
existing dry-run and safety gates.
