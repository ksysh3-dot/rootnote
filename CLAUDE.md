# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트

Rootnote는 RootlessJamesDSP 1.6.14(업스트림 커밋 `60d25ae`)의 비공식 포크다. 안드로이드 앱(Kotlin)에 폰 내장 스피커용 자체 C++ 엔진 `app/src/main/cpp/libpvb`(스피커 보정 EQ, 가상 저음, true-peak 리미터)를 더했다. GPL-3.0이고, 언어는 영어와 한국어만 낸다.

- 업스트림 코드는 패키지 `me.timschneeberger.rootlessjamesdsp`에 그대로 있다. Rootnote가 더한 코드는 주로 그 아래 `pvb/`와 `libpvb`에 있다.
- 업스트림 파일을 고쳤다면 `tools/list_modified_upstream.sh --write`로 `NOTICE.md`의 생성 구역을 갱신한다.
- `fastlane/`, `BUILD_ROOT.md`는 쓰지 않는 업스트림 잔재다.

## 명령

**APK 빌드**
- 필요한 것: JDK 17, Android SDK 35, NDK, CMake 3.22.1, 서브모듈 `libjamesdsp`(`git submodule update --init`).
- `./gradlew assembleRootlessFdroidGeneralRelease`: 공개 일반판.
- `assembleRootlessFdroidS26uRelease`: 개인 S26 Ultra 채널.
- `assembleRootFdroidGeneralRelease`: 루트 기기용.
- `GENERAL_*` 서명 비밀값이 없으면 디버그 키로 서명된 시험 빌드가 된다. 배포 절차는 `RELEASE_GENERAL.md`에 있다.

**호스트 엔진 시험** (Linux 전용, Windows에서는 WSL)
- `tools/pvb-harness/build_host.sh [출력폴더]`가 `build/libpvbcapi.so`(Python ctypes용 C API)와 `libpvbengine.so`(JNI)를 만든다. `-Werror`로 빌드한다.
- 시험은 pytest가 아니라 각각 독립 스크립트다. 한 개만 돌릴 때:
  `OPENBLAS_NUM_THREADS=1 python3 tools/pvb-harness/test_engine.py --report out.json`
- 연구 계열 시험은 `--lib tools/pvb-harness/build/libpvbcapi.so`를 받는다. 의존성은 `numpy scipy soundfile`.
- **CI가 실제로 돌리는 전체 목록과 순서는 `.github/workflows/build.yml`의 engine-tests 단계가 기준이다.**
- `test_experimental.py`, `test_devmode.py`는 `--baseline-ref <커밋>`으로 기존 출력과의 동일성을 본다.

**정적 검사**
- `python3 tools/test_static.py`: unittest. 한 항목만 돌릴 때는 `python3 tools/test_static.py <Class.test_name>`.
- `python3 tools/check_motion.py`: `docs/DESIGN.md` 6장 움직임 규칙.
- `test_static.py`는 리플렉션 이름, 매니페스트, 시작 순서, 버전·노트·README 일치를 검사한다. 버전을 올리면 `buildSrc/src/main/kotlin/AndroidConfig.kt`, `RELEASE_NOTES_GENERAL.md`, README가 서로 맞아야 한다.

**JVM 시험**
- `tools/pvb-harness/jvm/bootstrap_kotlin.sh`가 출력하는 `KOTLINC`, `KOTLIN_STDLIB`를 export한 뒤 `tools/pvb-harness/jvm/run_jvm_test.sh`를 돌린다.
- 순수 Kotlin `pvb` 클래스를 시험하고, JNI 출력과 C API 출력의 비트 일치를 확인한다.

**CI 동작**
- 모든 브랜치 push에서 돈다. 단, 문서만 바뀐 push(`**.md`, `docs/**`)는 빌드하지 않는다.
- engine-tests가 끝나면 APK 작업이 이어지고, 결과는 아티팩트로 올라간다: `PVB-S26U-test-apk`, `Rootnote-<버전>`, `Rootnote-JamesDSP-module`.
- 릴리스는 서명된 `general-v*` 태그에서만 만든다.

## 구조

### 앱

**변형(flavor)**
- 축이 셋이다: `version`(rootless/root/plugin) × `dependencies`(fdroid/full) × `device`(s26u/general).
- `general`은 공개판이다.
  - 패키지 `kr.ksysh3.rootnote`, 일반판 안전 상한 `SafeCaps.GENERAL`.
  - 마이크 foreground service 권한이 들어가면 CI가 실패한다. 녹음·버즈 진단·라이브 A/B 화면은 s26u 전용이다.
- `s26u`는 연구 도구가 들어간 개인 채널이고, 배포하지 않는다.

**설정이 스피커까지 가는 길**
- `PvbSettings` → `PvbBuild.finish`(상한·첫 실행 확인) → `PvbController.effective/push` → `PvbEngineParams.encode`(Android 클래스 없는 순수 함수) → `PvbNative`/`PvbEngine` → `pvb_jni.cpp` → `Engine`.
- 블록 단위 경로(JamesDSP만 / PVB만 / JamesDSP 뒤 PVB)는 `RootlessAudioProcessorService`의 `JdspChain.route`가 정한다.
- 각 모드의 소유자 표는 `PvbRuntime` 머리말에 있다.
- 자세한 설명은 `docs/ARCHITECTURE.md`에 있다. 코드와 다르면 코드가 맞다.

**모델**
- 엔진 ID는 `VbAlgo`(`pvb_vb.h`)이고, 앱 목록은 `pvb/PvbModels.kt`다.
- 저장 키(`alpha2_p1` 등)와 ID는 바꾸지 않는다. 바뀔 수 있는 것은 표시 이름(`title`)뿐이다.
- 기본값은 P1(ID 6)이다.

**UI**
- `docs/DESIGN.md`(색 토큰, 글자, 움직임, 하지 말 것)를 따른다.

### 엔진 (`libpvb`)

**처리 순서**
- 샘플별 순서는 `Engine::process`(`pvb_engine.cpp`)에 있고, 표로는 `docs/ARCHITECTURE.md` 3장에 있다.
- 입력 → 지연 맞춘 드라이 → 공간(`Xtc`) → EQ → 가상 저음 층 → 혼합 × 출력 → look-ahead 리미터.

**가상 저음 (`VbHpv`)**
- 코드는 `pvb_vb.h`/`.cpp`에 있고, P1 계열은 `pvb_vb52.cpp`에 있다.
- P1 계열은 hpv52m의 엄격한 인과(causal) 포트다. 기준 구현은 `tools/pvb-harness/vb51/hpv51.py`다.
- 내부 3 kHz 코어에서 이 순서로 처리한다:
  1. 대역 LR4 32–190 Hz
  2. HPSS(지속/타격 분리)
  3. 위상 보코더 트랙(`renderTrack52`, 배음 k = 2..8)과 타격 층(`bandLayer`)
  4. 포락선 이득(as/ps, 감쇠만)
  5. 출력 필터(`kOutSos`)
  6. 리샘플

**생성된 표**
- `pvb_vb_tables.h`, `pvb_vb52_tables.h`는 생성된 상수 표다. 손으로 고치지 않는다.
- 머리 주석에 생성 스크립트가 적혀 있지만, 그 스크립트가 저장소에 없을 수도 있다. 값이 바뀌면 P1의 소리가 바뀐다.
- 연구 브랜치에서 표를 새로 만들 때는 생성 스크립트를 함께 커밋한다(예: `research_r1_phase_table.py`).

**호스트 도구**
- `tools/pvb-harness/pvb_capi.cpp`가 Python 하네스용 C API다.
- 공용 렌더러는 `research_p1plus.render`다. 스템(생성층)과 출력을 함께 준다.
- 내부 신호 탭은 `vb_quality/stage_capture.py`(`COLUMNS`)에 있다.
- 트랙 기록은 `test_harmonic_continuity.tracks`로 읽는다.

### 연구 변형의 규칙

**호스트 연구 플래그로만 만든다**
- 연구 변형은 저장되는 앱 모드가 아니라 호스트 연구 플래그로만 만든다.
- 해당 플래그: `StageResearchFlag`(`pvb_vb_stage.h`, P1 프로필에만 적용), `pvb_set_p1plus_research`, `pvb_set_p1pp_*`.
- **플래그 0(그리고 기존 플래그)의 출력은 이전 빌드와 비트 단위로 같아야 한다.**
- 확인 방법: 옛 라이브러리와 새 라이브러리로 같은 입력을 렌더하고 output과 stem의 해시를 비교한다. CI의 baseline-ref 시험도 함께 본다.

**stage flag를 더할 때** (다음 2의 거듭제곱 값)
- `VbHpv::setStageResearch`의 마스크(`pvb_vb.h`)를 고친다.
- `pvb_stage_attach`의 상한(`pvb_capi.cpp`)을 고친다.
- `test_track_prediction_research.py`의 거부·허용 경계 목록을 고친다.

**앱으로 올릴 때**
- 새 모델 ID와 키로 추가한다.
- 기존 모델의 소리를 바꾸지 않는다.

**연구 문서**
- main에 있는 것: `docs/P1PP_*.md`, `docs/P1PLUS_*.md`, `research/`.
- 연구 브랜치에 있는 것: `docs/STUDY*_PREREG.md`, `docs/RESULTANT_*.md`.
- 개발군으로 먼저 개발한다. 확인군 seed는 동결 태그 뒤에 한 번만 연다. 실패한 후보도 기록한다.
- 연구 문서는 한국어로 쓴다. 코드 주석과 커밋 메시지는 영어로 쓴다.

## 사용자 결정 사항

- main 병합, 릴리스(`general-v*` 태그), 앱 기본 모델 변경은 사용자가 결정한다.
- 사용자의 음원과 비교 음원은 로컬에서만 쓴다. 커밋하지 않는다.

## 형식 검증 자동 적용 정책

### 기본 원칙
일반 개발에서는 기존 단위·통합·회귀 테스트를 우선한다. 형식 검증 스킬 `/proof-skills:formal-verify`는 기본으로 실행하지 않는다. 기존 테스트만으로 핵심 안전성을 충분히 확인하기 어렵고 실제 오류 위험이 높은 경우에만 선택적으로 쓴다.

### 실행 조건
다음 중 하나에 해당하고 검증의 실익이 충분하면 쓴다.
- 동시성, 비동기 작업, 취소, 재시작, 지연 응답, 중복 실행 같은 사건 순서 때문에 상태 충돌이 생길 수 있는 경우
- 반복되거나 재현하기 어려운 핵심 오류를 기존 테스트만으로 확인하기 어려운 경우
- 핵심 상태 관리, 프로토콜, API 계약을 바꾸면서 반드시 지켜야 할 규칙을 검증해야 하는 경우

### 실행 제외
- UI, 문서, 단순 기능 및 스타일 수정
- 기존 테스트만으로 충분히 검증할 수 있는 변경
- 검증 비용에 비해 실익이 낮은 작업
- 관련 모듈을 고쳤지만 핵심 안전성에는 영향이 없는 작업

### 검증 방법
1. 기존 검증 모델과 증명을 먼저 재사용하고, 영향받는 범위만 검사한다.
2. 사건 순서와 상태 전환 문제에는 TLA+/TLC를, 수학적 성질이나 불변 조건 증명이 필요하면 Lean 4를 고른다.
3. 검증 규칙은 기존 코드만이 아니라 요구사항, 계약, 과거 오류를 기준으로 정한다.
4. 모델의 상태·동작이 실제 코드와 어떻게 대응하는지 확인하고, 사용한 가정과 검사 범위를 기록한다.
5. 새로 만들거나 바꾼 핵심 모델은 가능한 범위에서 일부러 잘못된 조건을 넣어 오류 검출 능력을 확인한다.
6. 찾은 반례는 실제 코드에서 재현하고, 고친 뒤 기존 테스트와 형식 검증을 다시 실행한다.

### 안전 규칙
- 검사 실패, 미실행, 시간 초과, 미완성 증명은 성공으로 보지 않는다.
- 검증을 통과시키려고 기존 요구사항이나 불변 조건을 약화하지 않는다.
- 검증을 통과했다는 이유만으로 방어 코드를 임의로 지우지 않는다.
- 제한된 모델의 검사 통과를 전체 프로그램의 무결성 증명으로 해석하지 않는다.
- 이미 검증된 핵심 규칙에 영향을 주는 변경은 관련 검증을 다시 실행한다.

### 효율 및 보고
- 평소에는 기존 테스트를 쓰고, 불필요한 모델 생성과 반복 검증을 피한다.
- 실행했으면 검증 범위, 결과, 가정, 실제 코드 대응, 남은 위험을 간결하게 보고한다.
- 실행을 생략했으면 핵심 판단 근거만 짧게 남긴다.
- 도구를 실행할 수 없으면 성공한 것처럼 보고하지 않는다.
- 분석만 요청받았으면 사용자 승인 없이 기존 코드를 고치지 않는다.

목표: 일반 개발의 속도와 토큰 효율을 유지하면서, 복잡한 핵심 오류에만 검증 비용을 집중한다.
