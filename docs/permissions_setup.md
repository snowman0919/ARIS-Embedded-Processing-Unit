# ARIS Permission Setup

이 문서는 ARIS 개발/시뮬레이션/하드웨어 연동에 필요한 권한과 `chmod`,
`setfacl` 명령을 정리한다. 저장소 자체는 일반 개발자 권한으로 동작해야 하며,
관리자 권한은 Docker/디바이스 접근을 처음 열 때만 필요하다.

아래 명령은 기본 소유자를 `sbeen`, 공동 작업자를 `kotori9`로 가정한다. 다른
계정을 쓰면 먼저 변수를 바꾼다.

```bash
ARIS_REPO=/home/sbeen/aris/aris-dev-env
ARIS_OWNER=sbeen
ARIS_COLLAB=kotori9
```

## 필요한 권한

| 영역 | 필요 권한 | 목적 |
| --- | --- | --- |
| 저장소 파일 | 소유자 읽기/쓰기, 스크립트 실행 | 코드 수정, smoke test 실행 |
| 공유 작업자 | 선택: 지정 사용자 또는 그룹 `rwX` ACL | `sbeen`, `kotori9` 등 공동 작업 |
| Docker | `docker` 그룹 | ROS2/Gazebo/embedded 컨테이너 실행 |
| GPU | `render`, `video` 그룹 또는 `/dev/dri`, `/dev/nvidia*` ACL | CUDA, Gazebo/RViz 렌더링 |
| Serial MCU | `dialout`, `tty` 그룹 또는 `/dev/ttyUSB*`, `/dev/ttyACM*` ACL | MCU bridge, firmware flashing |
| USB sensor | `/dev/bus/usb/*` ACL 또는 udev rule | LiDAR, camera, debug probe |
| Camera | `video` 그룹 또는 `/dev/video*`, `/dev/media*` ACL | perception pipeline |
| Input device | `input` 그룹 또는 특정 joystick/event ACL | teleop, emergency/manual controller |
| CAN/SocketCAN | net admin 작업은 관리자/privileged helper | `can0`, `vcan0` bring-up |
| Data/cache | `~/aris/data`, `~/aris/logs`, `~/aris/models` 쓰기 | 로그, 모델, rosbag, map snapshot |

## 저장소 권한 정리

현재 저장소에 world-writable(`777`, `666`) 파일이 섞이면 빌드와 협업에서
권한 문제가 재발한다. 기본 원칙은 디렉터리 `755`, 일반 파일 `644`, 실행
스크립트 `755`이다.

```bash
ARIS_REPO=/home/sbeen/aris/aris-dev-env
ARIS_OWNER=sbeen

cd "$ARIS_REPO"

# 소유권이 다른 사용자로 남아 있을 때만 실행한다.
# sudo를 쓰지 않는 환경이라면 Docker root helper로 대체할 수 있다.
sudo chown -R "${ARIS_OWNER}:${ARIS_OWNER}" "$ARIS_REPO"

# 기본 모드: 디렉터리 755, 파일 644.
find "$ARIS_REPO" -type d \
  -not -path '*/.git/*' \
  -exec chmod 755 {} +

find "$ARIS_REPO" -type f \
  -not -path '*/.git/*' \
  -exec chmod 644 {} +

# 실행 파일만 다시 열기.
find "$ARIS_REPO/scripts" -type f -name '*.sh' \
  -exec chmod 755 {} +

chmod 755 "$ARIS_REPO/docker/ros_entrypoint.sh"
```

sudo 없이 Docker로 소유권만 복구해야 하는 경우:

```bash
ARIS_REPO=/home/sbeen/aris/aris-dev-env
ARIS_OWNER=sbeen

docker run --rm \
  -v "$ARIS_REPO:/repo" \
  ubuntu:24.04 \
  chown -R "$(id -u "$ARIS_OWNER"):$(id -g "$ARIS_OWNER")" /repo
```

## 공동 작업자 ACL

여러 사용자가 같은 working tree를 만질 때는 `chmod 777` 대신 ACL을 쓴다.
아래는 `sbeen`과 `kotori9`에게 읽기/쓰기 권한을 주되, 실행 비트는 디렉터리와
기존 실행 파일에만 적용하는 설정이다.

```bash
ARIS_REPO=/home/sbeen/aris/aris-dev-env
ARIS_OWNER=sbeen
ARIS_COLLAB=kotori9

setfacl -R \
  -m "u:${ARIS_OWNER}:rwX" \
  -m "u:${ARIS_COLLAB}:rwX" \
  "$ARIS_REPO"

setfacl -R \
  -m "d:u:${ARIS_OWNER}:rwX" \
  -m "d:u:${ARIS_COLLAB}:rwX" \
  "$ARIS_REPO"
```

그룹으로 관리할 경우:

```bash
sudo groupadd -f arisdev
sudo usermod -aG arisdev "$ARIS_OWNER"
sudo usermod -aG arisdev "$ARIS_COLLAB"

sudo chgrp -R arisdev "$ARIS_REPO"
chmod -R g+rwX,o-rwx "$ARIS_REPO"

setfacl -R -m g:arisdev:rwX "$ARIS_REPO"
setfacl -R -m d:g:arisdev:rwX "$ARIS_REPO"
```

## 데이터/로그/모델 디렉터리

런타임 산출물은 저장소 밖의 `~/aris` 아래에 둔다.

```bash
ARIS_HOME=/home/sbeen/aris
ARIS_OWNER=sbeen
ARIS_COLLAB=kotori9

mkdir -p "$ARIS_HOME/data" "$ARIS_HOME/logs" "$ARIS_HOME/models"
chmod 755 "$ARIS_HOME"
chmod 2775 "$ARIS_HOME/data" "$ARIS_HOME/logs" "$ARIS_HOME/models"

setfacl -m "u:${ARIS_OWNER}:rwx" \
  -m "d:u:${ARIS_OWNER}:rwx" \
  "$ARIS_HOME/data" "$ARIS_HOME/logs" "$ARIS_HOME/models"

# 공동 작업자가 필요할 때만 추가한다.
setfacl -m "u:${ARIS_COLLAB}:rwx" \
  -m "d:u:${ARIS_COLLAB}:rwx" \
  "$ARIS_HOME/data" "$ARIS_HOME/logs" "$ARIS_HOME/models"
```

## Docker/GPU/Serial 그룹

그룹 멤버십은 로그인 세션을 다시 열어야 반영된다.

```bash
ARIS_OWNER=sbeen

for group in docker dialout tty video render input plugdev netdev i2c spi gpio; do
  if getent group "$group" >/dev/null; then
    sudo usermod -aG "$group" "$ARIS_OWNER"
  fi
done

id "$ARIS_OWNER"
```

## 세션용 디바이스 ACL

아래 `setfacl`은 현재 연결된 디바이스에만 적용된다. 재부팅 또는 재연결 후에는
udev rule이 더 적합하다.

```bash
USER_NAME=sbeen

# MCU serial, USB serial, debug probe serial.
for dev in /dev/ttyACM* /dev/ttyUSB*; do
  [ -e "$dev" ] && sudo setfacl -m "u:${USER_NAME}:rw" "$dev"
done

# Camera/media devices.
for dev in /dev/video* /dev/media*; do
  [ -e "$dev" ] && sudo setfacl -m "u:${USER_NAME}:rw" "$dev"
done

# GPU render nodes.
for dev in /dev/dri/renderD* /dev/nvidia*; do
  [ -e "$dev" ] && sudo setfacl -m "u:${USER_NAME}:rw" "$dev"
done

# Joystick/manual controller. event*는 키보드/마우스를 포함할 수 있으므로
# 가능하면 /dev/input/by-id 경로에서 대상 장치를 확인한 뒤 적용한다.
for dev in /dev/input/js*; do
  [ -e "$dev" ] && sudo setfacl -m "u:${USER_NAME}:rw" "$dev"
done
```

특정 USB 장치를 확인한 뒤 ACL을 줄 때:

```bash
lsusb
ls -l /dev/bus/usb/*/*

# 예시: bus 001, device 004
sudo setfacl -m "u:${USER_NAME}:rw" /dev/bus/usb/001/004
```

## CAN/SocketCAN

CAN은 일반 파일 권한이나 `setfacl` 대상이 아니다. 인터페이스 생성/설정은
관리자 권한 또는 repository의 privileged helper가 맡고, 일반 노드는 올라온
`can0`/`vcan0`에 접속한다.

```bash
# 실제 CAN 장치 예시. bitrate는 하드웨어 설정에 맞춘다.
sudo ip link set can0 down || true
sudo ip link set can0 up type can bitrate 500000

# vcan은 제공된 helper를 우선 사용한다.
/home/sbeen/aris/aris-dev-env/scripts/can_create_vcan0.sh
```

## GUI/X11

RViz/Gazebo GUI를 컨테이너에서 띄울 때 현재 데스크톱 사용자에게 X11 접근을
허용한다.

```bash
ARIS_OWNER=sbeen

xhost "+SI:localuser:${ARIS_OWNER}"

if [ -n "${XAUTHORITY:-}" ] && [ -e "$XAUTHORITY" ]; then
  setfacl -m "u:${ARIS_OWNER}:r" "$XAUTHORITY"
fi
```

## 확인 명령

```bash
ARIS_REPO=/home/sbeen/aris/aris-dev-env
ARIS_OWNER=sbeen

cd "$ARIS_REPO"

find . -maxdepth 3 -type f -perm -0002 -printf '%M %u:%g %p\n' | sort
find scripts -type f ! -perm -0100 -printf 'missing execute: %p\n'
getfacl -p "$ARIS_REPO" | sed -n '1,80p'
id "$ARIS_OWNER"
```
