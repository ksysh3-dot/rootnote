# 일반 배포 빌드 (General build) — Rootnote

이 문서는 일반 배포 빌드(flavor `general`)의 구조, 서명 키 준비, 배포 절차, 남은 과제를 적습니다. 이 저장소(`ksysh3-dot/rootnote`, 공개)가 일반 빌드의 배포 저장소입니다: 서명 Secrets는 이 저장소에 두고, 릴리스는 이 저장소의 `general-v*` 태그로만 만듭니다.

## 1. 두 빌드

| | s26u (개인 채널) | general (일반 배포) |
|---|---|---|
| Gradle 변형 | `rootlessFdroidS26uRelease` | `rootlessFdroidGeneralRelease` (다른 조합은 비활성) |
| 패키지 | `kr.ksysh3.pvb.s26u` | `kr.ksysh3.rootnote` (`AndroidConfig.GENERAL_APPLICATION_ID`) |
| 앱 이름 | PVB | Rootnote (`AndroidConfig.GENERAL_BRAND_NAME` → 리소스 `app_brand_name`) |
| 버전 | 1.6.23-alpha3.3 / 61 | 0.9.0-beta.9 / 1008 (`generalVersionName`/`generalVersionCode`) |
| 서명 | 개인 채널 키 `app/pvb-signing.jks` (공개 저장소에는 없음: 파일이 없으면 디버그 키 = 시험용) | 환경 변수(GitHub Secrets)의 배포 키, 없으면 디버그 키 = 시험용 |
| `RESEARCH_UI` | true (연구 도구 항상 표시) | false (정보 화면의 버전을 7번 누르면 "개발자/연구" 표시) |
| `RECORD_FEATURES` | true | false: 곡별 세기 기억, 실청·고정 블라인드 비교 기록, 버즈 진단(녹음·마이크·5초 음악 클립·내보내기), 측정이 없음 |
| 안전 상한 | 없음 (기존 UI 범위) | 출력 ≤ −3 dB, 리미터 상한 ≤ −1 dBTP, 저중역 ≤ +6 dB, Q ≤ 2, 저역 차단 ≥ 80 Hz, 회복 ≥ 30 ms, 가상 저음 0~9 dB |
| 기기 프로파일 | 없음 (기존 기본값) | `assets/pvb_profiles/*.json`: S26 Ultra(SM-S948*) → `s26u`, 그 밖 → `neutral` + 1회 안내 |
| 첫 실행 | 없음 | 안내를 확인하기 전에는 처리 꺼짐, 서비스 시작 불가 |
| 언어 | 기존과 같음 | 영어 기본 + 한국어 (`resourceConfigurations`로 다른 언어 제외) |
| 아이콘 | upstream 아이콘 | 같은 아이콘, 배경색만 청록색(#0B7A7A, 심해 틸) (`src/general/res/mipmap-anydpi-v26`). 새 아이콘은 아직 없음 |
| 첫 화면 | DSP 화면 (MainActivity) | 홈 화면 (`home/HomeActivity`, Compose). DSP 화면은 "고급 설정"으로 엶 |
| 테마 색 | upstream 기본 | 기본 테마가 심해 틸 (`src/general/res/values*/themes_rootnote.xml`). 다른 테마 선택은 그대로 |

### 이름·패키지 바꾸기

`buildSrc/src/main/kotlin/AndroidConfig.kt`의 한 줄입니다.

- 앱 이름: `GENERAL_BRAND_NAME`. 런처·타일·정보 화면·첫 실행 안내·상태 카드가 모두 `app_brand_name`을 씁니다. upstream 문자열 중 앱 이름이 들어가던 것은 이름 없는 문장으로 바꿨습니다(`src/general/res/values*/strings_overrides.xml`).
- 패키지: `GENERAL_APPLICATION_ID`. ADB 명령, 권한 이름, CI의 패키지 확인이 여기서 나옵니다. 패키지를 바꾸면 이미 설치한 사람은 새 앱으로 다시 설치해야 합니다.
- 소스 주소: `app/src/main/res/values/strings_general.xml`의 `source_url` (기본 `https://github.com/ksysh3-dot/rootnote`).

## 2. 배포 키 만들기 (소유자가 한 번)

키는 저장소에 넣지 않습니다. 자신의 PC에서 만들고, 파일과 비밀번호를 안전한 곳(비밀번호 관리자 등)에 따로 백업합니다. **키를 잃어버리면 같은 패키지로 업데이트를 낼 수 없습니다.**

```sh
keytool -genkeypair -v \
  -keystore rootnote-release.jks -storetype PKCS12 \
  -alias rootnote -keyalg RSA -keysize 4096 -validity 10000 \
  -dname "CN=Rootnote, O=ksysh3"
# 비밀번호를 두 번 묻습니다(PKCS12는 저장소·키 비밀번호가 같습니다).

# GitHub Secret에 넣을 base64 한 줄
base64 -w0 rootnote-release.jks > rootnote-release.jks.b64      # Linux
# macOS: base64 -i rootnote-release.jks -o rootnote-release.jks.b64
# Windows PowerShell: [Convert]::ToBase64String([IO.File]::ReadAllBytes("rootnote-release.jks")) > rootnote-release.jks.b64

# 인증서 지문(사용자에게 공개해 설치본 검증에 씀)
keytool -list -v -keystore rootnote-release.jks -alias rootnote | grep SHA256
```

### GitHub Secrets 4개

이 저장소(`ksysh3-dot/rootnote`)의 Settings → Secrets and variables → Actions → New repository secret:

| 이름 | 값 |
|---|---|
| `GENERAL_KEYSTORE_B64` | `rootnote-release.jks.b64` 파일 내용 (한 줄) |
| `GENERAL_KEYSTORE_PASSWORD` | 키 저장소 비밀번호 |
| `GENERAL_KEY_ALIAS` | `rootnote` |
| `GENERAL_KEY_PASSWORD` | 키 비밀번호 (PKCS12면 저장소 비밀번호와 같음) |

`gh` CLI로는 `gh secret set GENERAL_KEYSTORE_B64 --repo ksysh3-dot/rootnote < rootnote-release.jks.b64` 처럼 넣을 수 있습니다.

CI는 `GENERAL_KEYSTORE_B64`를 `$RUNNER_TEMP/general.jks`로 풀고 `GENERAL_KEYSTORE_PATH`로 Gradle에 넘깁니다. 로컬 빌드에서는 같은 네 환경 변수(또는 `GENERAL_KEYSTORE_PATH`)를 설정하면 됩니다. 하나라도 없으면 general APK는 디버그 키로 서명되고 CI 아티팩트 이름이 `…-UNSIGNED-TEST`로 끝납니다. 이 APK는 시험용이며 배포하면 안 됩니다(러너마다 키가 달라 업데이트가 안 됨).

## 3. 배포 절차

1. 이 저장소(`ksysh3-dot/rootnote`, GPL-3.0 대응 소스)에 위 Secrets 4개를 넣습니다. 저장소 주소가 바뀌면 `source_url`도 고칩니다.
2. `main`의 CI(엔진 시험 + 두 빌드)가 통과했는지 확인합니다.
3. 태그를 올립니다(태그 이름의 버전은 `AndroidConfig.generalVersionName`과 같게): `git tag general-v0.9.0-beta.9 && git push origin general-v0.9.0-beta.9`.
4. CI가 엔진 시험 → 두 빌드 → 서명 확인(키가 없으면 실패) → 릴리스를 만듭니다. 첨부: `Rootnote-0.9.0-beta.9.apk`, `.sha256`, `source-<커밋>.tar.gz`(서브모듈 포함 소스). 버전에 `-`가 있으면 사전 릴리스로 표시됩니다.
5. 다음 버전은 `AndroidConfig.generalVersionName`/`generalVersionCode`를 올린 뒤 새 태그를 붙입니다.

브랜치 푸시와 풀 리퀘스트는 두 빌드를 아티팩트로만 올리고 릴리스를 만들지 않습니다. s26u 변형(개인 채널)은 이 공개 저장소에서 시험 빌드(디버그 키, 아티팩트 `PVB-S26U-test-apk`)만 하며 릴리스하지 않습니다.

## 4. 개발자/연구 메뉴 (general)

설정 → 정보 → 버전을 7번 누르면 열립니다(4번째부터 남은 횟수 안내). 열리면:

- DSP 화면: PVB 카드 아래 "개발자/연구" 머리말과 분석 카드
- PVB 카드: 모델 목록(코드명), Q·고음 기울기 슬라이더, 볼륨 연동 슬라이더(스위치는 항상 보임), 조용한 구간 저음
- 상태 카드: 볼륨 dB 출처, 폰 리미터 추정(S26U 프로파일에서만), 부하, 설정 변화 기록, 저음 연구 기록 복사
- 정보 화면: "개발자/연구 도구 숨기기"

안전 상한은 연구 메뉴를 열어도 그대로입니다. 기록을 저장하는 기능(버즈 진단·블라인드 비교·측정·곡별 기억)은 general에 아예 없습니다: 매니페스트에서 화면·서비스·프로바이더·`FOREGROUND_SERVICE_MICROPHONE` 권한을 제거했고, `BuildConfig.RECORD_FEATURES = false`로 코드 경로(서비스 인텐트, 진단 무장, 곡 감시, 알림 채널)를 막았습니다. `RECORD_AUDIO`는 시스템 오디오 캡처 자체에 필요해서 남깁니다.

## 5. 기기 프로파일

- `app/src/general/assets/pvb_profiles/s26u.json`: `samsung` + 모델 접두어 `SM-S948`. `SM-S948N`은 측정한 기기에서 확인. 다른 지역 접미어(B, U, U1, W, 0 등)는 **TODO-confirm**. `SM-S938*`(S25 Ultra)은 일부러 제외.
- `neutral.json`: 저역 차단 120 Hz, 저중역 +2 dB(220 Hz), 고역 −2 dB(4.5 kHz) — 실측된 안드로이드 92기종 중 약한 쪽 끝에 맞춘 보수적 시작값(docs/SPEAKER_ESTIMATES.md), 고음 기울기 0, 출력 −3 dB, 상한 −1 dBTP, 끌 때 음량 맞춤·볼륨 연동·조용한 구간·가상 저음 꺼짐. 음량 맞춤을 끄므로 S26U 스피커 가중 필터는 쓰이지 않고, S26U 곡선(분석 화면 스피커 반영, 폰 리미터 추정)은 표시하지 않습니다.
- 처음 설치할 때 한 번만 `pvb_settings`에 씁니다(`pvb_device_profile` 키로 기록). 이후 값은 사용자 것입니다. 측정되지 않은 기기에서는 첫 실행 안내(시작 안내)의 첫 쪽에서 조심스러운 시작값을 알리고, 상태 카드에도 한 줄 표시합니다. 시작 안내를 확인하면 따로 있던 "이 기기는 측정되지 않았습니다" 대화상자는 띄우지 않습니다.
- 새 기기를 추가하려면 JSON 파일을 하나 더 넣습니다(`settings` 키는 `DeviceProfiles.FLOAT_KEYS`/`BOOL_KEYS`만 읽음).

## 6. 홈 화면 (general)

승인된 디자인(E안, 팔레트 "심해 틸")을 Jetpack Compose로 구현했습니다(`app/src/general/java/.../home/`). Compose UI 의존성은 general에만 들어가고, s26u에는 Compose 컴파일러 플러그인이 요구하는 runtime만 들어갑니다(s26u 화면은 그대로).

- 맨 위 줄 전체가 처리 스위치입니다. 켜기 = `pvb_enable` + `pvb_vb_enable` 켜고 서비스가 꺼져 있으면 캡처 권한 요청. 끄기 = `pvb_enable`만 끔(서비스는 계속 돌아 다시 켤 때 캡처 창이 다시 뜨지 않음). 첫 실행 안내 전에는 켤 수 없고(안내를 먼저 띄움), 가상 저음이 꺼져 있던 상태에서 켜면 고급 화면과 같은 실험 기능 경고를 띄웁니다.
- 첫 실행 안내는 일곱 쪽짜리 전체 화면입니다(`home/WelcomeActivity.kt`, `WelcomeScreen.kt`, 문자열 `welcome_*`). 한 쪽에 한 메시지: "반가워요!"(가운데, 앱 표시가 움직임으로 그려짐) / 가상 저음(이 폰의 시작값 포함) / 공간감(위에서 본 그림) / 약 0.15초 지연과 앱별 제외 / 켜기 전에 알아 두세요(볼륨 주의, 실험 기능, 내장 스피커만, 다른 효과 앱) / 준비는 한 번이면 돼요(권한, 캡처 동의 창, Android 15 개발자 옵션) / 이제 시작해 볼까요?(동의 문장, 개인정보, 라이선스, [나중에] [확인하고 시작하기]). 그림은 그 쪽에 올 때 한 번 재생되고 멈춥니다. 확인·동의 창 줄은 그 폰의 Android 버전에 맞는 것만 보입니다. "확인하고 시작하기"가 예전 "확인하고 켜기"와 같은 하나의 동의입니다. "나중에"를 고르면 그 실행 동안 홈이 다시 띄우지 않고, 처리를 켤 때 마지막 쪽부터 엽니다. 처음 실행에서 권한이 없으면 시작 안내 다음에 설정 화면으로 갑니다.
- 문장: 저음을 채우고 있어요(서비스 + PVB + 가상 저음) / 스피커 보정만 쓰고 있어요(가상 저음만 꺼짐) / 원래 소리로 듣고 있어요.
- 세기 슬라이더 0~9 dB(general 상한), 칩 3개는 고급 화면 모드 목록과 같은 규칙(모델 + 세기)으로 선택이 정해집니다. "사용자 지정"을 누르면 프리셋 칩을 누를 때까지 그 상태로 남습니다.
- 볼륨 연동 줄은 컨트롤러가 쓰는 `VolumeLevelLink` 계산 그대로입니다(서비스가 돌 때는 컨트롤러가 공개한 볼륨, 아니면 같은 AudioManager 값).
- 판단 로직은 `pvb/HomeLogic.kt`(순수 Kotlin), 시험은 `tools/pvb-harness/jvm/HomeLogicTest.kt`(문자열 영어/한국어 짝 확인 포함).
- 시스템 "애니메이션 제거"(애니메이터 배율 0)이면 모든 움직임이 즉시 바뀝니다.

## 7. 시험

- 호스트 JVM: `tools/pvb-harness/jvm/run_jvm_test.sh`에 `GeneralBuildTest.kt` 추가(실제 asset으로 프로파일 일치, 상한 적용, 첫 실행 게이트, ADB 명령, 백업 제외 XML).
- 홈 화면: `HomeLogicTest.kt`(칩 선택, 상한, 첫 실행 게이트, 볼륨 연동 줄, 문자열). CI는 general APK의 런처가 `HomeActivity` 하나인지, s26u 런처가 `MainActivity`인지 확인합니다.
- 앱 빌드는 CI에서만 합니다(로컬 Android SDK 없음). 실기기 확인은 아직 하지 않았습니다: 첫 실행 안내 흐름, Shizuku/ADB 설정, 다른 제조사 기종, 정보 화면, 언어 전환.

## 8. 알려진 과제 (known debt)

- **한국어 하드코딩 문자열**: Kotlin 소스에 한국어 리터럴이 약 349줄(주석 제외, 30개 파일) 남아 있습니다. general에서 보이는 것은 주로 상태 카드(`PvbStatusView.kt`), 모델 이름(`PvbModels.kt`, 연구 메뉴), 경로 이름(`PvbController.kt`)입니다. 나머지는 general에 없는 기능(블라인드 비교, 측정, 버즈 진단)입니다.

  | 파일 | 줄 수 |
  |---|---|
  | `pvb/PvbAbCard.kt` | 59 (general에 없음) |
  | `pvb/LiveAbView.kt` | 45 (general에 없음) |
  | `pvb/PvbStatusView.kt` | 38 |
  | `pvb/PvbMeasure.kt` | 34 (general에 없음) |
  | `pvb/PvbAnalyzerView.kt` | 24 (연구 메뉴) |
  | `activity/BuzzReportsActivity.kt` | 23 (general에 없음) |
  | `pvb/PvbMeasureCard.kt` | 19 (general에 없음) |
  | `pvb/PvbAbConditions.kt` | 19 (general에 없음) |
  | `pvb/LiveAbComparisons.kt` | 18 (general에 없음) |
  | `pvb/PvbModels.kt` | 15 (연구 메뉴, general 프리셋은 리소스 사용) |
  | `utils/notifications/ServiceNotificationHelper.kt` | 7 (버즈 알림, general에 없음) |
  | `pvb/BuzzDiagnostics.kt` | 7 (general에 없음) |
  | `pvb/PvbAnalyzerCard.kt` | 6 (연구 메뉴) |
  | `service/BuzzMicrophoneService.kt` | 5 (general에 없음) |
  | `pvb/PvbController.kt` | 5 |
  | 그 밖 15개 파일 | 1~4줄씩 (대부분 주석 속 예시나 s26u 전용 경로) |

- PVB 문자열 리소스(`strings_pvb.xml`)는 영어 기본 + `values-ko` 한국어로 나눴습니다. upstream 문자열은 upstream 영어·한국어 번역을 그대로 씁니다.
- 새 아이콘 없음(배경색만 바꿈). 버전·이름 외 브랜딩(스크린샷, 스토어 문구)은 없음.
- JamesDSP 카드들을 "고급(JamesDSP 엔진)" 아래로 모으는 정리는 하지 않았습니다.
- arm64 전용, R8 꺼짐, 재현 빌드 아님, targetSdk 34는 그대로입니다.
- 서드파티 라이선스 목록은 `PvbGeneral.THIRD_PARTY`와 `assets/licenses/THIRD_PARTY.txt`에 손으로 적었습니다(oss-licenses 플러그인 없음). 의존성을 바꾸면 함께 고쳐야 합니다.
- NOTICE.md의 수정 파일 목록은 `tools/list_modified_upstream.sh --write`로 갱신합니다(비교 기준인 upstream 커밋을 먼저 가져와야 함: 스크립트 머리말 참고).
