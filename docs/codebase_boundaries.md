# Codebase Boundaries

ARIS is split into separate repositories so each program has a clear runtime and ownership boundary.

## ARIS-Embedded-Processing-Unit

This repository contains the ROS 2 processing-unit stack:

- ROS 2 packages under `src/`
- simulation and Gazebo/RViz launch paths
- localization, perception, mapping, planning, bringup, and MCU bridge ROS nodes
- Docker/Nix development environment
- processing-unit verification scripts and documentation

It should not contain the standalone Flutter operator interface or standalone MCU firmware sources.
It may contain processing-unit handoff artifacts and exporters, such as GUI snapshot JSON produced
from route CSV or V3 SemanticHDMap snapshots, plus the localhost snapshot bridge used by the
external Flutter operator console.

## ARIS-Flutter-Interface

The Flutter operator console lives in `snowman0919/ARIS-Flutter-Interface`.

Local working copy convention:

```bash
/home/sbeen/aris/aris-flutter-interface
```

## ARIS-Embedded-MCU

The STM32F446 safety MCU firmware lives in `snowman0919/ARIS-Embedded-MCU`.

## ARIS-AI

The DGX Spark AI/Isaac/ROS lab environment lives in `snowman0919/ARIS-AI`.

Local working copy convention:

```bash
/home/sbeen/aris/dgx-spark-ai-lab
```
