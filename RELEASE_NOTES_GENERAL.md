**Rootnote** — phone speaker virtual bass · unofficial RootlessJamesDSP fork
(폰 스피커 가상 저음 · RootlessJamesDSP 기반 비공식 포크)

Beta for Android 10+ (arm64). Not made or supported by the RootlessJamesDSP/JamesDSP developers. GPL-3.0, no warranty.
The corresponding source is the tagged commit; `source-*.tar.gz` below contains it with the `libjamesdsp` submodule.

- Setup needs Shizuku or ADB once (the app shows the exact commands for its package on first start).
- Android 15+: turn on "Disable screen share protections" in Developer options.
- Apps that block audio capture (Spotify, Chrome, SoundCloud, ...) play unprocessed.
- Measured settings exist only for the Galaxy S26 Ultra; other phones start with conservative neutral settings.
- Privacy: only settings are stored; no song titles, no recordings, nothing sent (see PRIVACY.md).

## What's new: battery and CPU (이번 버전: 배터리와 CPU)

소리는 그대로 두고 계산량만 줄였습니다. 엔진 출력은 이전 버전과 비트 단위로 같습니다(19가지 설정, x86-64와 폰과 같은 ARM64 빌드에서 확인).

처리 부하 (음악 40초, 48 kHz, 서버 CPU 한 코어 기준. 폰에서는 수치가 다르고, 줄어드는 비율이 비슷할 것으로 예상합니다):

| 설정 | 이전 | 이번 |
|---|---|---|
| 기본 (가상 저음 P1) | 30.7% | 4.8% |
| 가상 저음 끔 | 2.8% | 0.5% |
| S26U 측정 설정 | 31.5% | 5.9% |
| D2 / J2 | 32.1% / 36.5% | 4.8% / 6.2% |
| 무음 | 3.5% | 0.9% |

- 저음 떨림 맞춤을 다른 풀이 방법으로 바꿨습니다(이전 부하의 76%). sin/cos는 벡터화했고, 리미터는 조용한 구간에서 계산을 건너뜁니다.
- 무음 휴식: 소리가 정한 시간(2/5/10초, 기본 2초) 동안 없으면 출력을 쉬게 해서 스피커 앰프가 대기에 들어갈 수 있게 합니다. 다시 재생하면 잘림 없이 이어집니다. "유휴 시 절전" 설정을 따릅니다.
- 깊은 절전 (선택, 기본 꺼짐): 출력이 30초/1분/5분 쉬었고 재생 중인 것이 없으면 캡처도 멈춰 폰이 잠들 수 있게 합니다. 켜 두면 재생을 다시 시작할 때 처음 0.1초 정도가 잘릴 수 있습니다. 잠든 동안에는 알림에 "깊은 절전 중"이 표시됩니다.
- 화면에 표시만 하는 값(폰 리미터 추정)은 그 화면을 볼 때만 계산합니다.

자세한 내용: `docs/PERFORMANCE.md`

Verify the download with the `.sha256` file.
