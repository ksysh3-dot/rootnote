# 개인정보 안내 / Privacy

이 문서는 일반 배포 빌드 **Rootnote**(패키지 `kr.ksysh3.rootnote`)에 대한 것입니다. 개인용 S26U 빌드(`kr.ksysh3.pvb.s26u`)의 차이는 맨 아래에 적었습니다.

This document covers the general distribution build **Rootnote** (package `kr.ksysh3.rootnote`). The differences of the personal S26U build (`kr.ksysh3.pvb.s26u`) are at the end.

---

## 한국어

### 요약

- 이 앱은 **설정만** 폰 안에 저장합니다.
- **곡 제목·아티스트·앨범, 오디오 녹음, 마이크 녹음, 사용 기록을 저장하지 않습니다.** 이런 정보를 저장하던 연구 기능(곡별 세기 기억, 블라인드 비교 기록, 버즈 진단 녹음·내보내기, 측정)은 일반 빌드에 들어 있지 않습니다.
- **어디에도 보내지 않습니다.** 분석·광고·오류 보고(Firebase 등) 라이브러리가 없습니다.
- 유일한 네트워크 접속은 사용자가 JamesDSP 이퀄라이저에서 **AutoEQ 검색**을 쓸 때입니다. 이때 원본 프로젝트의 AutoEQ 서버(`aeq.timschneeberger.me`, 설정에서 주소 변경 가능)에 검색어를 보냅니다.

### 폰 안에 저장하는 것

| 무엇 | 위치 | 내용 |
|---|---|---|
| 스피커 보정·가상 저음 설정 | `shared_prefs/pvb_settings.xml` | EQ·출력·리미터·가상 저음 값, 적용한 기기 프로파일 이름 |
| 앱 상태 | `shared_prefs/pvb_flags.xml` | 첫 실행 안내 확인 여부, 개발자/연구 메뉴 표시 여부, "측정되지 않은 기기" 안내 표시 여부 |
| 음량 맞춤 값 | `shared_prefs/pvb_match_cache.xml` | 마지막 음량 맞춤 dB 값 하나 |
| 분석 화면 표시 옵션 | `shared_prefs/pvb_ui.xml` | 개발자/연구 메뉴의 분석 그래프 표시 선택(연구 메뉴를 열었을 때만) |
| JamesDSP 설정(원본 기능) | `shared_prefs/` 의 `dsp_*`, 앱 설정 파일 | 이퀄라이저·효과·앱 옵션 |
| 제외 앱 목록(원본 기능) | 앱 데이터베이스 | 처리에서 뺄 앱의 패키지 이름(사용자가 직접 추가한 경우) |
| 프리셋·스크립트·IR 파일(원본 기능) | 앱 파일 영역 | 사용자가 직접 만들거나 가져온 파일 |
| 진단 로그(원본 기능) | 캐시 `application.log` | 기술 메시지(최대 2 MB, 앱을 시작할 때마다 새로 씀). 처리 중인 앱 이름이 들어갈 수 있습니다. 설정 › 문제 해결에서 직접 공유하지 않는 한 폰 밖으로 나가지 않습니다. |

시스템 오디오는 서비스가 켜져 있는 동안 메모리에서만 처리하고 저장하지 않습니다. 오디오 캡처에는 Android 규정상 `RECORD_AUDIO` 권한이 필요합니다. 마이크는 두 경우에만 씁니다. 공간감의 '좌우 맞추기'에서 사용자가 **자동 측정**을 직접 누르면, 20~45초 동안 폰의 위아래 마이크로 두 스피커 소리를 듣고 메모리에서 대역별 크기만 계산한 뒤 버립니다. 녹음은 저장하지도, 어디로 보내지도 않습니다.

마이크를 쓰는 곳이 하나 더 있습니다. 개발자 모드의 **저음 맞추기**는 시작할 때와 1단계 동안 폰 마이크로 방 소음과 스피커 소리를 듣고, 메모리에서 대역별 크기만 계산한 뒤 버립니다. 녹음은 저장하지 않습니다. 저음 맞추기의 **검증 모드**는 회차별 결과 숫자(시각, 기기 모델, 앱 버전, 볼륨, 찾은 주파수나 세기, 답의 개수, 방 소음 여유, 마이크 종류, 폰이 알려 준 마이크 감도)를 앱 내부 파일 `files/bass_fit_validation.csv`에 남깁니다. 검증 모드의 **마이크 맞추기**는 녹음 방식별 대역 크기(숫자)와 기기 모델을 `files/bass_fit_mic_cal.csv`에 남깁니다. 두 파일 모두 소리나 곡 정보는 들어 있지 않고, 화면의 공유 버튼으로만 밖에 나가며, 지우기 버튼으로 지울 수 있습니다. 클라우드 백업에도 포함되지 않습니다.

### 백업

`pvb_*` 파일(위 표의 앞 네 줄)은 Android 클라우드 백업과 기기 간 전송에서 **제외**됩니다. JamesDSP 설정 등 원본 기능의 설정은 Android 백업 설정에 따라 사용자의 Google 백업에 포함될 수 있습니다.

### 권한

| 권한 | 용도 |
|---|---|
| 오디오 녹음(RECORD_AUDIO) | 다른 앱의 소리를 캡처하는 데 필요. 마이크는 '좌우 맞추기' 자동 측정(20~45초)과 개발자 모드 '저음 맞추기'(시작과 1단계) 때만 씀(녹음 저장 안 함) |
| 화면/오디오 캡처(PROJECT_MEDIA, 셸에서 한 번 부여) | 캡처 시작 시 동의 창 생략 |
| DUMP(셸에서 한 번 부여) | 재생 중인 오디오 세션 감지 |
| 알림 | 처리 상태 표시 |
| 인터넷 | AutoEQ 검색(선택) |
| 부팅 완료, 다른 앱 위에 표시(선택) | 재부팅 뒤 자동 시작 |
| 사용 정보 접근(선택) | '제외한 앱을 쓰는 동안 완전히 멈추기'를 켰을 때만: 지금 메인 화면에 있는 앱의 패키지 이름을 1초마다 확인(저장 안 함, 기록 안 남김) |

### 지우기

앱을 삭제하면 위의 모든 데이터가 지워집니다. 설정 › 앱 › Rootnote › 저장공간 › 데이터 삭제로도 지울 수 있습니다.

---

## English

### Summary

- The app stores **only its settings** on the phone.
- It **does not store song titles, artists or albums, audio recordings, microphone recordings or usage history.** The research features that stored such data (per-song strength memory, blind comparison records, buzz diagnostics recordings and exports, measurement) are not part of the general build.
- **Nothing is sent anywhere.** There are no analytics, advertising or crash reporting libraries (no Firebase).
- The only network access is the **AutoEQ search** in the JamesDSP equalizer, when you use it: the search text is sent to the AutoEQ server of the original project (`aeq.timschneeberger.me`, changeable in the settings).

### What is stored on the phone

| What | Where | Contents |
|---|---|---|
| Speaker correction and virtual bass settings | `shared_prefs/pvb_settings.xml` | EQ, output, limiter and virtual bass values; name of the device profile applied |
| App state | `shared_prefs/pvb_flags.xml` | first-run notice confirmed, developer/research menu shown, "not measured" notice shown |
| Loudness match | `shared_prefs/pvb_match_cache.xml` | one number: the last loudness match in dB |
| Analysis view options | `shared_prefs/pvb_ui.xml` | display choices of the analysis graph (only if the research menu was opened) |
| JamesDSP settings (upstream) | `dsp_*` and app settings files in `shared_prefs/` | equalizer, effects, app options |
| Excluded apps (upstream) | app database | package names of apps you excluded from processing |
| Presets, scripts, impulse responses (upstream) | app files | files you created or imported |
| Diagnostic log (upstream) | cache `application.log` | technical messages (at most 2 MB, rewritten at every start); may contain names of processed apps. It leaves the phone only if you share it yourself under Settings, Troubleshooting. |

System audio is processed in memory while the service runs and is never saved. Android requires the `RECORD_AUDIO` permission for audio capture itself. The microphone is used in two cases only. First: when you tap **Measure automatically** in spatial "Even out the speakers", the phone listens to its two speakers with its top and bottom microphones for about 20-45 s, computes the level per band in memory and discards the audio. Nothing is saved or sent.

The microphone is used in one more place. **Bass fit** in developer mode listens to the room and the speaker with the phone microphone at its start and during step 1, computes the level per band in memory and discards the audio; no recording is saved. Its **validation mode** keeps the numbers of each run (time, phone model, app version, volume, the frequency or strength found, answer counts, room margin, microphone source, the microphone sensitivity the phone declares) in the app's own file `files/bass_fit_validation.csv`; its **microphone match** keeps the level per band of each recording source (numbers) and the phone model in `files/bass_fit_mic_cal.csv`. Neither holds audio or song information, leaves the phone only through the share button on that screen, can be deleted with the clear button, and is not part of cloud backup.

### Backup

The `pvb_*` files (first four rows above) are **excluded** from Android cloud backup and device-to-device transfer. Upstream settings such as the JamesDSP settings may be part of your Google backup, depending on your Android backup settings.

### Permissions

| Permission | Purpose |
|---|---|
| Record audio (RECORD_AUDIO) | required to capture the audio of other apps; the microphone only during "Even out the speakers" automatic measuring (about 20-45 s) and developer-mode "Bass fit" (its start and step 1); no recording is saved |
| Screen/audio capture (PROJECT_MEDIA, granted once from a shell) | starting capture without the consent dialog |
| DUMP (granted once from a shell) | detecting active audio sessions |
| Notifications | processing status |
| Internet | AutoEQ search (optional) |
| Boot completed, display over other apps (optional) | automatic start after reboot |
| Usage access (optional) | only with "Pause fully while an excluded app is in front": checks which app is the main window once a second (package name only, never stored) |

### Deleting

Uninstalling the app deletes all of the above. You can also use Settings, Apps, Rootnote, Storage, Clear data.

---

## 개인용 S26U 빌드 / Personal S26U build (`kr.ksysh3.pvb.s26u`)

S26U 빌드에는 연구 기능이 그대로 있어 다음도 저장할 수 있습니다(모두 사용자가 직접 켤 때만, 기기 밖으로는 공유 버튼으로만 나감): 곡별 세기 기억(`pvb_track_levels`: 곡 제목·아티스트·앨범·재생 앱), 블라인드 비교 기록(`pvb_ab`, `files/live_ab/`: 곡 정보·볼륨·배터리), 측정 결과(`pvb_measure`), 버즈 진단(`pvb_buzz`, `files/buzz_reports/`: 최근 5초 음악 PCM, 선택 시 마이크 녹음). 이 파일들도 클라우드 백업과 기기 간 전송에서 제외됩니다.

The S26U build keeps the research features and can also store the following (each only when you turn it on; it leaves the phone only through the share buttons): per-song strength memory (`pvb_track_levels`: song title, artist, album, player app), blind comparison records (`pvb_ab`, `files/live_ab/`: song information, volume, battery), measurement results (`pvb_measure`), buzz diagnostics (`pvb_buzz`, `files/buzz_reports/`: the last 5 s of music as PCM and, if enabled, a microphone recording). These files are excluded from cloud backup and device transfer as well.
