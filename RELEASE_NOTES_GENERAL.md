**Rootnote** — phone speaker virtual bass · unofficial RootlessJamesDSP fork
(폰 스피커 가상 저음 · RootlessJamesDSP 기반 비공식 포크)

Beta for Android 10+ (arm64). Not made or supported by the RootlessJamesDSP/JamesDSP developers. GPL-3.0, no warranty.
The corresponding source is the tagged commit; `source-*.tar.gz` below contains it with the `libjamesdsp` submodule.

- Setup needs Shizuku or ADB once (the app shows the exact commands for its package on first start).
- Android 15+: turn on "Disable screen share protections" in Developer options.
- Apps that block audio capture (Spotify, Chrome, SoundCloud, ...) play unprocessed.
- Measured settings exist only for the Galaxy S26 Ultra; other phones start with conservative neutral settings.
- Privacy: only settings are stored; no song titles, no recordings, nothing sent (see PRIVACY.md).

## 0.9.0-beta.2: 0.9.0-beta.1 이후 바뀐 것

폰 내장 스피커로 듣는 음악의 저음과 공간감을 살려 주는 앱 Rootnote의 베타 업데이트예요. 써 보시고 느낀 점을 알려 주시면 큰 도움이 돼요.

### 새로 생긴 것

**공간감 (기본 꺼짐)**
- 폰을 가로로 들고 들을 때 좌우를 넓혀 주는 기능이에요.
- 프리셋은 은은하게 / 균형 / 확실하게 세 가지예요. 듣는 거리와 머리 크기도 고를 수 있어요.
- 「좌우 맞추기」로 아래 스피커와 위 스피커의 음량 차이를 맞출 수 있어요. 폰 마이크로 먼저 재고, 귀로 확인한 뒤 저장해요.
- 세로로 들면 꺼지고, 원하면 모노나 2웨이(저음은 아래, 고음은 위 스피커)로 바꿀 수 있어요.
- 홈 화면의 (i)를 누르면 원리를 움직이는 그림으로 설명해 줘요.

**JamesDSP 효과와 함께 쓰기**
- JamesDSP 효과를 먼저 거치고 Rootnote가 마지막에 처리해요.
- 겹치는 효과(베이스 부스트, 아날로그 모델링, 출력 제어)는 Rootnote가 켜져 있는 동안 잠겨요. 설정은 그대로 남아 있어요.
- 공간감이 켜져 있으면 JamesDSP 「음장 넓이」도 잠겨요. 넓히기는 하나만 켜지게 했어요.

**제외한 앱을 쓰는 동안 완전히 멈추기 (기본 꺼짐)**
- 인스타그램이나 유튜브에서 음소거해 둔 영상이 Rootnote를 거쳐 들리는 문제를 막아요.
- 제외한 앱이 메인 화면에 있으면 Rootnote가 통째로 멈춰요.
- PIP 작은 창이나 떠 있는 창은 메인으로 치지 않아요. 그래서 유튜브를 PIP로 띄워 두고 음악을 들으면 음악은 계속 처리돼요.
- '사용 정보 접근' 권한이 필요해요.

**개발자 모드**
- 배음 세기, 지속음·타격음 세기 같은 값을 직접 만지고, 그래프로 바로 확인할 수 있어요.

**절전**
- 한동안 조용하면 출력을 쉬어요(2초 / 5초 / 10초 중 선택).
- 「딥 슬립」을 켜면 오래 조용할 때 녹음까지 멈춰요. 다시 깨어날 때 첫 0.1초쯤 잘릴 수 있어요.

### 바뀐 것

- 홈 화면, 첫 실행 안내, 고급 설정, 설정, 제외할 앱 화면을 모두 새 디자인으로 바꿨어요.
- 새 기본 테마는 「심해 틸」이에요. 예전 테마는 「원본 기본값」으로 남아 있어요.
- 아이콘이 새로 바뀌었어요.
- 가상 저음 기본 세기를 +6에서 +4로 낮췄어요. 큰 볼륨에서 나던 지지직거림(버즈)이 확실히 줄었어요.
- 볼륨이 커지면 가상 저음을 알아서 줄이는 기능을 기본으로 켰어요.
- 처리 부담(CPU)을 약 5분의 1로 줄였어요. 소리는 똑같아요.
- 처음 켤 때 동의를 한 번만 받아요. 설치 안내도 짧아졌고, 배터리 설정 안내가 새로 생겼어요.
- 시스템이 앱을 강제로 끄면 홈 화면에 알려 줘요.
- 영상·게임·통화 앱을 골라서 바로 제외에 넣을 수 있어요.

### 고친 것

- 좌우 맞추기: 마이크 하나를 두 개로 잘못 알아보던 문제, 귀로 확인하러 들어가기만 해도 저장되던 문제를 고쳤어요. 맞추는 동안 JamesDSP 효과가 섞이던 문제도 고쳤어요.
- 세로 2웨이에서 가상 저음이 위쪽 스피커로도 나오던 문제를 고쳤어요.
- 가상 저음을 켤 때 0.2초쯤 끊기던 문제를 고쳤어요.
- 라이트 모드에서 원래 보라색이 보이던 문제를 고쳤어요.
- 그 밖에 자잘한 버그를 고쳤어요.

### 솔직한 한계

- 공간감이 실제 귀에서 얼마나 효과가 있는지는 아직 측정하지 못했어요. 계산으로 추정한 값만 있어요.
- 공간감은 일반적인 넓히기 효과와 달리 자세와 거리에 아주 민감해요. 많이 움직이거나 비스듬히 들으면 소리가 한쪽으로 쏠리거나 음색이 어색해질 수 있어요. 누워서 보거나 걸으면서 듣는다면 끄시는 걸 권해요.
- 좌우 맞추기 측정에는 피할 수 없는 오차가 있어요. 그래서 꼭 귀로 확인한 뒤 저장하게 되어 있어요.
- 처리된 소리는 약 0.15초 늦게 나와요. 영상이나 게임은 제외에 넣어 주세요.
- 「제외한 앱을 쓰는 동안 완전히 멈추기」는 앱 전환을 1초마다 확인해요. 그래서 멈추고 다시 켜지는 데 1~2초 걸릴 수 있어요.
- 갤럭시 S26 Ultra 말고 다른 기기에서는 아직 거의 확인하지 못했어요.

Verify the download with the `.sha256` file.
