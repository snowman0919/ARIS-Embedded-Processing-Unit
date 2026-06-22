# ARIS 프로젝트 현황 문서

작성일: 2026-06-19 KST

## 1. 요약

현재 `/home/sbeen/aris` 폴더는 소스 코드 저장소라기보다 ARIS ROS 2 시스템의 실행 산출물 보관 폴더에 가깝다. 확인된 구성은 다음과 같다.

- `data/`: 현재 비어 있음
- `models/hf/`: 현재 비어 있음
- `models/torch/`: 현재 비어 있음
- `logs/ros/`: ROS 2 launch 및 노드 로그
- `logs/bags/aris_verify_130829/`: 검증용 rosbag2 MCAP 기록

상위 폴더에는 `README`, `package.xml`, `setup.py`, `CMakeLists.txt`, `*.launch.py` 같은 소스/패키지 정의 파일이 없다. 로그 안에는 `/workspaces/aris/install/...` 경로가 반복적으로 등장하지만, 현재 환경에서는 `/workspaces/aris` 경로가 존재하지 않는다. 따라서 이 문서는 현재 폴더에 남아 있는 로그와 bag 메타데이터를 기준으로 프로젝트 흐름을 역추적한 내용이다.

## 2. 폴더 구조

```text
/home/sbeen/aris
├── data/
├── logs/
│   ├── bags/
│   │   └── aris_verify_130829/
│   │       ├── aris_verify_130829_0.mcap
│   │       └── metadata.yaml
│   └── ros/
│       ├── 2026-06-18-.../launch.log
│       ├── 2026-06-19-.../launch.log
│       ├── python3_*.log
│       ├── robot_state_publisher_*.log
│       ├── static_transform_publisher_*.log
│       └── tf2_echo_*.log
└── models/
    ├── hf/
    └── torch/
```

관찰 결과:

- 전체 폴더 용량은 약 780 KB이다.
- ROS 로그 파일은 91개이고, 그중 내용이 있는 파일은 35개이다.
- bag 산출물은 약 544 KB이며, 실제 MCAP 데이터는 약 526 KB이다.
- `data`, `models/hf`, `models/torch`는 비어 있다.

## 3. 프로젝트 성격 추정

로그와 토픽 구성을 보면 ARIS는 ROS 2 Jazzy 기반의 차량/로봇 주행 시뮬레이션 또는 제어 검증 프로젝트로 보인다.

핵심 흐름은 다음으로 추정된다.

1. 차량 시뮬레이터가 차량 상태와 휠 오도메트리를 생성한다.
2. 로컬 플래너 또는 teleop 입력이 주행 명령을 만든다.
3. MCU 브리지가 주행 명령을 받아 하위 제어 계층으로 넘긴다.
4. robot_state_publisher와 TF가 좌표계를 제공한다.
5. rosbag2가 주요 토픽을 기록해 검증 증거를 남긴다.

로그에 등장한 주요 노드는 다음과 같다.

- `vehicle_sim_node`: 차량 시뮬레이션 노드
- `local_planner_node`: 로컬 주행 명령 생성 노드
- `mcu_bridge_node`: MCU 브리지 노드
- `mcu_bridge_sim`: 초기 시뮬레이션용 MCU 브리지
- `teleop_node`: `/cmd_vel`을 `/cmd_drive`로 변환하는 teleop 브리지
- `robot_state_publisher`: 로봇 모델 기반 TF 발행
- `static_transform_publisher`: `map -> odom` 정적 transform 발행
- `rosbag2_recorder`: 토픽 기록
- `rviz2`: 시각화 도구
- `talker`, `aris_smoke_listener`: 초기 ROS pub/sub smoke test

## 4. 실행 흐름 타임라인

### 2026-06-18: 초기 ROS/시뮬레이션 검증

초기 로그에는 ROS 기본 통신 확인과 시뮬레이션 조합 실행 흔적이 있다.

- `talker`가 `Hello World` 메시지를 발행했다.
- `aris_smoke_listener`가 해당 메시지를 정상 수신했다.
- `vehicle_sim_node`와 `mcu_bridge_sim` 조합이 실행됐다.
- 이후 `local_planner_node`가 추가되어 `vehicle_sim_node + local_planner_node + mcu_bridge_sim` 조합으로 반복 실행됐다.
- RViz 실행 시도도 있었으나 한 세션에서 `exit code -6`으로 종료됐다.

이 단계의 의미:

- ROS 2 런타임과 기본 pub/sub는 동작했다.
- 시뮬레이터와 MCU 시뮬 브리지, 로컬 플래너 조합까지 실행이 진행됐다.
- RViz 시각화는 환경 또는 그래픽 설정 이슈가 남아 있을 가능성이 있다.

### 2026-06-19 21:40 KST 전후: TF/상태 발행 구성 추가

로그상 다음 노드들이 함께 실행됐다.

- `robot_state_publisher`
- `static_transform_publisher`
- `vehicle_sim_node`
- `local_planner_node`
- `mcu_bridge_node`

`mcu_bridge_node`는 다음 상태로 기동했다.

```text
ARIS MCU bridge up: DRY-RUN (no actuation). Heartbeat watchdog 200 ms.
```

`static_transform_publisher`는 다음 정적 transform을 발행했다.

```text
from 'map' to 'odom'
translation: 0, 0, 0
rotation: 0, 0, 0, 1
```

이 단계의 의미:

- 실제 액추에이션 없이 dry-run 모드로 브리지 검증을 수행했다.
- `map -> odom` TF 연결이 추가됐다.
- `robot_state_publisher`는 정상 초기화됐다.

### 2026-06-19 21:51 KST 전후: teleop 검증

`teleop_node` 로그에 다음 안내가 남아 있다.

```text
Teleop bridge up: run `ros2 run teleop_twist_keyboard teleop_twist_keyboard` to drive /cmd_vel -> /cmd_drive.
```

같은 세션에서 `robot_state_publisher`, `mcu_bridge_node`, `vehicle_sim_node`, `static_transform_publisher`, `teleop_node`가 실행됐다.

이 단계의 의미:

- 키보드 teleop 기반으로 `/cmd_vel` 입력을 받아 `/cmd_drive`로 변환하는 흐름이 준비됐다.
- MCU 브리지는 계속 dry-run 상태였다.

### 2026-06-19 21:52 KST 전후: rosbag 기록 시도

`rosbag2_recorder`가 `/aris/logs/bags/aris_20260619_125216`에 기록을 시작했다.

구독한 토픽:

- `/tf_static`
- `/estop`
- `/vehicle/state`
- `/tf`
- `/cmd_drive`
- `/odometry/filtered`
- `/wheel_odom`

이 단계의 의미:

- 검증에 필요한 주요 토픽 세트를 정의했다.
- 다만 현재 폴더에는 해당 bag 디렉터리 자체가 남아 있지 않고, 이후 생성된 `aris_verify_130829`만 존재한다.

### 2026-06-19 22:08 KST: 검증 bag 생성

현재 보존된 bag은 `logs/bags/aris_verify_130829`이다.

메타데이터 요약:

- ROS distro: Jazzy
- storage: MCAP
- 기록 시작: 2026-06-19 22:08:30 KST
- 기록 길이: 약 5.58초
- 총 메시지 수: 1,196개
- 파일: `aris_verify_130829_0.mcap`

기록된 토픽:

| Topic | Type | Message count |
| --- | --- | ---: |
| `/cmd_drive` | `ackermann_msgs/msg/AckermannDriveStamped` | 245 |
| `/wheel_odom` | `nav_msgs/msg/Odometry` | 279 |
| `/tf` | `tf2_msgs/msg/TFMessage` | 280 |
| `/odometry/filtered` | `nav_msgs/msg/Odometry` | 280 |
| `/vehicle/state` | `aris_interfaces/msg/StateReport` | 112 |

`rosbag2_recorder` 로그상 모든 요청 토픽 구독에 성공했고, 약 5초 후 기록이 일시정지 및 종료됐다.

## 5. 현재까지 현황

완료 또는 확인된 항목:

- ROS 2 Jazzy 기반 실행 흔적이 확인됐다.
- 기본 pub/sub smoke test가 성공했다.
- 차량 시뮬레이션 노드가 여러 차례 실행됐다.
- 로컬 플래너와 MCU 브리지 시뮬레이션 조합이 실행됐다.
- 실제 `mcu_bridge_node`가 dry-run 모드로 정상 기동했다.
- `robot_state_publisher`가 정상 초기화됐다.
- `map -> odom` 정적 transform 발행이 추가됐다.
- teleop 브리지가 `/cmd_vel -> /cmd_drive` 흐름을 준비했다.
- 검증 bag `aris_verify_130829`에 핵심 주행/상태/TF 토픽이 기록됐다.

아직 불명확하거나 남은 항목:

- 현재 폴더에는 소스 코드와 launch 파일이 없다.
- 로그가 참조하는 `/workspaces/aris` 경로가 현재 환경에 없다.
- 실제 차량 제어는 수행되지 않았고, MCU 브리지는 dry-run 모드였다.
- `/tf_static`, `/estop`은 이전 기록 시도에서는 구독 대상이었지만 현재 보존된 검증 bag에는 없다.
- RViz는 한 차례 `exit code -6`으로 비정상 종료됐다.
- `tf2_echo` 로그에는 과거에 `map`, `base_link`, `lidar_link` 연결이 완전하지 않았던 흔적이 있다.
- `data/`와 `models/`는 아직 비어 있어 데이터셋/모델 기반 기능은 현재 산출물만으로는 확인되지 않는다.

## 6. 시스템 흐름

현재 로그 기준의 데이터 흐름은 다음과 같이 볼 수 있다.

```text
teleop 또는 local_planner
        |
        v
    /cmd_drive
        |
        v
 mcu_bridge_node  -- dry-run, no actuation

vehicle_sim_node
        |
        +--> /wheel_odom
        +--> /vehicle/state
        +--> /odometry/filtered

robot_state_publisher + static_transform_publisher
        |
        +--> /tf
        +--> map -> odom

rosbag2_recorder
        |
        +--> logs/bags/aris_verify_130829/*.mcap
```

## 7. 검증 관점의 해석

`aris_verify_130829` bag은 짧지만 의미 있는 통합 검증 산출물이다.

- `/cmd_drive`가 245개 기록되어 명령 생성 흐름이 있었다.
- `/wheel_odom`과 `/odometry/filtered`가 각각 약 280개 기록되어 오도메트리 계열 출력이 안정적으로 발생했다.
- `/tf`가 280개 기록되어 TF 발행도 함께 동작했다.
- `/vehicle/state`가 112개 기록되어 차량 상태 리포트가 발행됐다.

5.58초 동안 1,196개 메시지가 기록된 점을 보면, 시뮬레이션/상태/TF/명령 루프가 동시에 살아 있었던 것으로 판단된다. 다만 bag 내용 자체의 수치 품질, 프레임 연결 완전성, 명령에 대한 차량 응답의 타당성은 현재 설치된 `ros2`/`mcap` CLI가 없어 메타데이터 수준까지만 확인했다.

## 8. 리스크와 정리 필요 사항

1. 소스 트리 부재
   - 현재 폴더만으로는 패키지 구조, launch 정의, 파라미터, 메시지 정의를 확인할 수 없다.
   - `/workspaces/aris` 또는 원본 git 저장소를 복구해야 유지보수 가능한 프로젝트 문서가 완성된다.

2. 실행 산출물 중심 구조
   - `logs/`는 잘 남아 있지만, 실행 재현 방법이 없다.
   - 현재 폴더에 `README.md`, 실행 스크립트, 환경 설정 파일이 필요하다.

3. dry-run 상태
   - `mcu_bridge_node`가 dry-run으로 떠 있으므로 하드웨어 액추에이션 검증은 아직 아니다.
   - 실제 MCU 연결 전 안전 조건, estop, heartbeat 정책을 문서화해야 한다.

4. TF 연결 이력
   - 과거 `tf2_echo`에서 `map`, `base_link`, `lidar_link` 연결 실패가 있었다.
   - 이후 `map -> odom`은 추가됐지만 전체 TF tree가 완전히 닫혔는지는 bag 재생 또는 라이브 실행으로 재검증해야 한다.

5. RViz 환경
   - RViz가 한 번 `exit code -6`으로 종료됐다.
   - GUI/디스플레이/컨테이너 그래픽 설정 또는 RViz config 호환성을 확인해야 한다.

## 9. 다음 단계 로드맵

### Phase 1. 프로젝트 복구와 기준선 확립

- 원본 소스 트리 또는 git 저장소를 현재 작업공간에 연결한다.
- 최소 문서 세트를 만든다.
  - `README.md`
  - 실행 환경 설치 절차
  - launch 명령
  - 주요 토픽 표
  - dry-run과 hardware-run의 차이
- `package.xml`, launch 파일, 파라미터 파일, URDF/Xacro, RViz config를 인벤토리화한다.
- 현재 bag `aris_verify_130829`를 기준 검증 산출물로 등록한다.

### Phase 2. 재현 가능한 시뮬레이션 실행

- `vehicle_sim_node + local_planner_node + mcu_bridge_node + TF` 조합을 하나의 launch로 재현한다.
- teleop 검증 launch와 autonomous/local planner 검증 launch를 분리한다.
- `ros2 topic hz`, `ros2 topic echo`, `tf2_tools view_frames` 등으로 기본 헬스체크를 자동화한다.
- RViz 실행 문제를 해결하고, 시뮬레이션 상태를 시각적으로 확인한다.

### Phase 3. Bag 기반 품질 검증

- bag 재생 절차를 문서화한다.
- `/cmd_drive`와 `/wheel_odom` 간 응답 관계를 분석한다.
- `/odometry/filtered`와 `/wheel_odom`의 차이를 확인한다.
- TF tree가 `map -> odom -> base_link -> sensor frames`로 끊김 없이 이어지는지 검증한다.
- `/vehicle/state` 메시지의 필드별 정상 범위와 상태 전이를 정의한다.

### Phase 4. 안전 계층과 MCU 연동 준비

- dry-run 모드의 입력/출력 경계를 명확히 한다.
- heartbeat watchdog 200 ms 정책을 테스트한다.
- `/estop` 토픽을 현재 검증 bag에도 포함한다.
- 실제 MCU 연결 전 checklist를 만든다.
  - estop 기본값
  - timeout 시 동작
  - 명령 saturation
  - steering/speed 단위
  - 로그/재현 절차

### Phase 5. 데이터와 모델 폴더 활용 계획

- `data/`에 bag 분석 결과, 평가 리포트, 캘리브레이션 데이터를 저장할 규칙을 만든다.
- `models/hf/`, `models/torch/`는 실제 ML 모델을 쓸 계획이 있을 때만 유지한다.
- 모델 기반 기능이 없다면 빈 모델 폴더는 제거하거나 “reserved” 문서를 둔다.

## 10. 바로 실행할 수 있는 액션 아이템

우선순위 높은 순서:

1. 원본 소스 트리를 확보한다.
2. `README.md`에 현재 실행 조합과 bag 검증 결과를 옮긴다.
3. `aris_verify_130829` bag을 재생해 토픽 값과 TF tree를 검증한다.
4. `/estop`과 `/tf_static`을 포함한 새 검증 bag을 다시 기록한다.
5. RViz 비정상 종료 원인을 해결한다.
6. dry-run에서 hardware-run으로 넘어가기 전 안전 체크리스트를 완성한다.

## 11. 결론

현재 폴더만 기준으로 보면 ARIS는 “소스가 들어 있는 개발 저장소”가 아니라 “ROS 2 차량 시뮬레이션/제어 검증 산출물 묶음”이다. 그래도 로그와 bag은 꽤 선명한 진전을 보여준다. 기본 ROS 통신, 시뮬레이터, 로컬 플래너/teleop, TF, dry-run MCU 브리지, rosbag 기록까지 연결됐고, 마지막 검증 bag에는 주행 명령과 오도메트리, TF, 차량 상태가 함께 기록됐다.

다음 전환점은 소스 트리 복구와 재현성 확보다. 그다음 bag 기반 품질 검증, TF/RViz 안정화, estop/heartbeat 중심의 안전 계층 정리를 거치면 실제 하드웨어 연동 준비 단계로 넘어갈 수 있다.
