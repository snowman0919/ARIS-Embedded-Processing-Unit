# ARIS Architecture Documents

이 폴더의 최상위 기준 문서는 `FINAL_ARCHITECTURE_SPEC.md`이다.

## 최종본

- `FINAL_ARCHITECTURE_SPEC.md`: PDF 설계서를 현재 저장소 기준으로 재구성한 한국어 최종 아키텍처 명세.

## 분야별 계약 문서

- `architecture_framework.md`: 전체 프레임워크 요약.
- `communication_protocol.md`: ROS2 topic, PC-MCU binary protocol, heartbeat, fault, transport 계약.
- `internal_structure.md`: package ownership, 제어 경계, pure core/ROS wrapper 구조.
- `workflows.md`: V0-V6, boot, goal navigation, map update, failure, safety workflow.
- `architecture_mapping.md`: PDF 요구사항과 현재 저장소 구현/gap 매핑.
- `verification_plan.md`: unit/integration/SIL/HIL/field 검증 기준.
- `permissions_setup.md`: 저장소/공동작업자/하드웨어 디바이스 권한과 `chmod`, `setfacl` 명령.

## 기존 빠른 참조

- `mcu_protocol.md`: MCU protocol 간단 요약.
- `safety.md`: 안전 규칙 요약.
- `sensors.md`: 센서 구성 요약.
- `ai_layer.md`: AI layer 금지/허용 범위 요약.
- `HANDOFF.md`: 구현 인수인계용 상세 메모.

## 문서 우선순위

충돌이 있으면 다음 순서로 해석한다.

1. `FINAL_ARCHITECTURE_SPEC.md`
2. 분야별 계약 문서
3. 기존 빠른 참조 문서
4. 과거 handoff/log 문서
