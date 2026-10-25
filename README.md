# Rootnote

**Phone speaker virtual bass and EQ for Android, based on RootlessJamesDSP 1.6.14.**

Rootnote is an **unofficial fork** of [RootlessJamesDSP](https://github.com/ThePBone/RootlessJamesDSP).
It is **not** made, endorsed or supported by the RootlessJamesDSP or JamesDSP developers. Please do not
report problems of this fork to the upstream projects.

[한국어 안내는 아래에 있습니다.](#한국어)

## What it does

Rootnote keeps the rootless system-wide audio capture of RootlessJamesDSP and adds its own engine for the
built-in speaker of a phone (`app/src/main/cpp/libpvb`):

- speaker correction EQ (protective low cut, low-mid lift, treble shaping),
- virtual bass: generated harmonics so that bass below what a small speaker can play is still heard,
- output level and a true-peak limiter,
- safe limits in the general build (output at most -3 dB, limiter ceiling at most -1 dBTP, bounded EQ).

While the speaker correction is on, it runs after the JamesDSP effects: captured audio goes through the
JamesDSP effects you have turned on, then through this engine, whose limiter is the last step. A few JamesDSP
effects that clash with it (dynamic bass boost, analog modelling, the JamesDSP output gain and limiter) are held off
while it processes and come back when it is off. When it is off, the JamesDSP features of the original app work as
before. Processing applies to the built-in speaker
only; headphones and Bluetooth are bypassed.

## Status

**Beta** (`0.9.0-beta.12`, Android 10 or later, arm64).

- The default settings were measured on a **Galaxy S26 Ultra** (model `SM-S948*`). Every other phone starts
  with a conservative neutral profile (120 Hz low cut, low-mid +2 dB, treble -2 dB, output -3 dB, limiter -1 dBTP; see docs/SPEAKER_ESTIMATES.md) and a
  one-time notice that it has not been measured. Adjust by ear.
- Nothing is processed before you confirm the first-run notice. Confirming it turns the speaker correction **and
  virtual bass** on (the notice carries the virtual-bass warning); the home screen switch turns processing off.
- Virtual bass is experimental: it adds about 0.15 s of delay, and the effect (and any buzzing) depends on
  the song and the phone.
- Apps that block audio capture (for example Spotify, Chrome, SoundCloud) play unprocessed. This limitation
  comes from Android and is the same as in RootlessJamesDSP.

## Install and setup

Download the APK from the [releases](https://github.com/ksysh3-dot/rootnote/releases) of this repository and
check it against the `.sha256` file next to it. The package name is `kr.ksysh3.rootnote`; it can be installed
next to the original RootlessJamesDSP, but do not run both at the same time.

No root is needed, but two permissions must be granted once from a shell. The app shows these steps on
first start, and processing stays off until you confirm that notice.

- **Shizuku** (recommended, no PC): install Shizuku, start it with wireless debugging, then allow access in
  the setup screens of the app.
- **ADB** (with a PC): enable USB debugging and run

  ```sh
  adb shell pm grant kr.ksysh3.rootnote android.permission.DUMP
  adb shell appops set kr.ksysh3.rootnote PROJECT_MEDIA allow
  adb shell appops set kr.ksysh3.rootnote SYSTEM_ALERT_WINDOW allow
  ```

  The last line is optional (automatic start after reboot).

On **Android 15 and later**, turn on "Disable screen share protections" in Developer options; otherwise
notifications are hidden while audio is captured.

## Privacy

Rootnote stores **only its settings** on the phone. It does not store song titles, artists, audio or
microphone recordings or usage history, and it sends nothing anywhere: there are no analytics, advertising or
crash reporting libraries. The only network access is the optional AutoEQ search of the JamesDSP equalizer,
which contacts the AutoEQ server of the original project. Details: [PRIVACY.md](PRIVACY.md).

## Building

Requirements: JDK 17, the Android SDK (compile SDK 35) with NDK and CMake 3.22.1, and the `libjamesdsp`
submodule.

```sh
git clone --recursive https://github.com/ksysh3-dot/rootnote
cd rootnote
./gradlew assembleRootlessFdroidGeneralRelease
```

Without signing secrets the general APK is signed with the debug key and is a **test build only**. Release
signing (environment variables / GitHub secrets `GENERAL_*`) and the release procedure are described in
[RELEASE_GENERAL.md](RELEASE_GENERAL.md).

The repository also contains a second flavor, `s26u`, the developer's personal Galaxy S26 Ultra channel
(package `kr.ksysh3.pvb.s26u`, with research tools). It is built by CI for testing but is not released from
this repository; in this public source it is signed with the debug key.

Host tests of the engine (no Android SDK needed, Linux, Python 3 with numpy, scipy and soundfile):

```sh
tools/pvb-harness/build_host.sh
python3 tools/pvb-harness/test_engine.py
tools/pvb-harness/jvm/bootstrap_kotlin.sh      # prints KOTLINC and KOTLIN_STDLIB to export
tools/pvb-harness/jvm/run_jvm_test.sh
```

The full list of host tests that CI runs is in [.github/workflows/build.yml](.github/workflows/build.yml).

## License and credits

Rootnote is free software under the **GNU General Public License version 3** ([LICENSE](LICENSE)), the same
licence as the original. It comes **without any warranty**.

- **RootlessJamesDSP** by Tim Schneeberger ([@ThePBone](https://github.com/ThePBone)): the app, rootless audio
  capture, JamesDSP integration and UI this fork is built on.
- **JamesDSP** / libjamesdsp by James Fung ([@james34602](https://github.com/james34602)): the DSP engine used
  when the speaker correction is off (submodule `app/src/main/cpp/libjamesdsp`).
- The translators of RootlessJamesDSP (Crowdin project "rootlessjamesdsp"). Rootnote ships only English and
  Korean.
- Third-party components and their licences are listed in the app (About, Third-party licenses) and in
  `app/src/general/assets/licenses/THIRD_PARTY.txt`.

What this fork changed, including the list of modified upstream files, is in [NOTICE.md](NOTICE.md).

### Upstream

For the original app, its downloads (Google Play, F-Droid), documentation, limitations and the Spotify
patch, see the [RootlessJamesDSP repository](https://github.com/ThePBone/RootlessJamesDSP). Those store
listings belong to the original app, not to Rootnote. The `fastlane/` directory and `BUILD_ROOT.md` in this
repository are upstream files kept unchanged; Rootnote does not use them.

---

## 한국어

**Rootnote**는 RootlessJamesDSP 1.6.14를 바탕으로 한 안드로이드용 **폰 스피커 가상 저음·EQ 앱**입니다.
[RootlessJamesDSP](https://github.com/ThePBone/RootlessJamesDSP)의 **비공식 포크**이며, RootlessJamesDSP나 JamesDSP
개발자가 만들거나 지원하는 앱이 아닙니다. 이 포크의 문제를 원본 프로젝트에 알리지 말아 주세요.

### 하는 일

RootlessJamesDSP의 루트 없는 시스템 오디오 캡처는 그대로 쓰고, 폰 내장 스피커용 엔진을 더했습니다.

- 스피커 보정 EQ(보호용 저역 차단, 저중역 보강, 고음 조정)
- 가상 저음: 작은 스피커가 내지 못하는 낮은 음을 배음으로 들리게 함
- 출력 레벨과 true-peak 리미터
- 일반 빌드의 안전 상한(출력 −3 dB 이하, 리미터 −1 dBTP 이하, EQ 범위 제한)

스피커 보정을 켜면 JamesDSP 효과 뒤에 이 엔진이 이어집니다. 캡처한 소리는 켜 둔 JamesDSP 효과를 먼저 거치고, 이 엔진을
지나며, 마지막 단계는 이 엔진의 리미터입니다. 이 엔진과 부딪히는 몇 가지 JamesDSP 효과(다이나믹 베이스 부스트, 아날로그
모델링, JamesDSP 출력 게인·리미터)는 처리하는 동안 멈췄다가 끄면 다시 적용됩니다. 끄면 원래 JamesDSP 기능이 그대로
동작합니다.
내장 스피커에서만 적용되며 이어폰·블루투스에서는 우회합니다.

### 상태

**베타**(`0.9.0-beta.12`, Android 10 이상, arm64)입니다.

- 기본 설정은 **갤럭시 S26 Ultra**(모델 `SM-S948*`)에서 측정했습니다. 다른 폰은 보수적인 중립 설정(보호용 저역 차단
  100 Hz, 평탄한 EQ, 출력 −3 dB, 리미터 −1 dBTP)으로 시작하고 "측정되지 않은 기기" 안내를 한 번 띄웁니다. 들으면서
  조정해 주세요.
- 처음 안내를 확인하기 전에는 아무것도 처리하지 않습니다. 안내를 확인하면 스피커 보정과 **가상 저음**이 함께 켜집니다
  (안내에 가상 저음 경고가 들어 있습니다). 홈 화면 스위치로 처리를 끌 수 있습니다.
- 가상 저음은 실험 기능입니다. 약 0.15초 지연이 있고, 효과(와 윙윙거림)는 곡과 기기에 따라 다릅니다.
- 오디오 캡처를 막는 앱(예: Spotify, Chrome, SoundCloud)의 소리는 처리되지 않습니다(안드로이드 제약, 원본과 같음).

### 설치와 설정

이 저장소의 [릴리스](https://github.com/ksysh3-dot/rootnote/releases)에서 APK를 받고 옆의 `.sha256` 파일로 확인하세요.
패키지 이름은 `kr.ksysh3.rootnote`입니다. 원본 RootlessJamesDSP와 함께 설치할 수 있지만 둘을 동시에 켜지는 마세요.

루트는 필요 없지만 셸 권한 두 가지를 한 번 줘야 합니다. 앱이 처음 실행될 때 같은 안내를 보여 주며, 안내를 확인하기
전에는 처리가 꺼져 있습니다.

- **Shizuku**(권장, PC 불필요): Shizuku를 설치하고 무선 디버깅으로 시작한 뒤, 앱의 설정 화면에서 접근을 허용합니다.
- **ADB**(PC 필요): USB 디버깅을 켜고 다음을 실행합니다.

  ```sh
  adb shell pm grant kr.ksysh3.rootnote android.permission.DUMP
  adb shell appops set kr.ksysh3.rootnote PROJECT_MEDIA allow
  adb shell appops set kr.ksysh3.rootnote SYSTEM_ALERT_WINDOW allow
  ```

  마지막 줄은 선택입니다(재부팅 뒤 자동 시작).

**Android 15 이상**에서는 개발자 옵션의 "화면 공유 보호 사용 중지"를 켜세요. 켜지 않으면 캡처 중에 알림이 가려집니다.

### 개인정보

Rootnote는 **설정만** 폰에 저장합니다. 곡 제목·아티스트, 오디오·마이크 녹음, 사용 기록을 저장하지 않고 어디에도
보내지 않습니다(분석·광고·오류 보고 라이브러리 없음). 네트워크는 JamesDSP 이퀄라이저의 선택 기능인 AutoEQ 검색(원본
프로젝트의 AutoEQ 서버)에만 씁니다. 자세한 내용: [PRIVACY.md](PRIVACY.md).

### 빌드

JDK 17, Android SDK(compile SDK 35)와 NDK, CMake 3.22.1, `libjamesdsp` 서브모듈이 필요합니다.

```sh
git clone --recursive https://github.com/ksysh3-dot/rootnote
cd rootnote
./gradlew assembleRootlessFdroidGeneralRelease
```

서명 비밀값이 없으면 일반 APK는 디버그 키로 서명되며 **시험용**입니다. 배포 서명(`GENERAL_*` 환경 변수/GitHub
Secrets)과 배포 절차는 [RELEASE_GENERAL.md](RELEASE_GENERAL.md)에 있습니다. 저장소의 `s26u` 변형은 개발자의 개인
S26 Ultra 채널(연구 도구 포함)이며, 이 저장소에서는 시험 빌드만 하고 배포하지 않습니다.

### 라이선스와 출처

**GNU GPL 3.0**([LICENSE](LICENSE)), 원본과 같은 라이선스이며 **보증은 없습니다**.
원본 앱은 Tim Schneeberger(@ThePBone)의 RootlessJamesDSP, DSP 엔진은 James Fung(@james34602)의 JamesDSP입니다.
바뀐 내용과 수정한 원본 파일 목록은 [NOTICE.md](NOTICE.md)에 있습니다. 원본 앱의 스토어 배포(Google Play,
F-Droid)와 문서는 [RootlessJamesDSP 저장소](https://github.com/ThePBone/RootlessJamesDSP)를 보세요. 그 스토어
목록은 원본 앱의 것이며 Rootnote의 것이 아닙니다.
