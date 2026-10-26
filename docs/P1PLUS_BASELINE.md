# P1+ 임시 채택: 연구 기준 고정

결정일: 2026-10-26. 사용자가 현재 HQ 결과를 **P1+**로 명명하고 임시 채택했다.
채택 범위는 **연구 기준**이다. Android 앱의 기본 모드 변경, 설정 화면과 APK 배포는 별도 작업이다.
이 결정은 10월 23일의 연구 중단 및 청감 AB 선행 조건을 연구 진행에 한해 대체한다.

## 정확히 무엇을 P1+라고 부르는가

| 이름 | P1 연구 플래그 | 내용 |
|---|---:|---|
| P1 | 0 | 기존 비교 기준 |
| phase-only 비교군 | 2 | 참조가 없을 때 위상 오프셋 유지. 역사 문서의 초기 P1+ |
| **P1+** | **6** | 위상 유지 + 앞뒤 5프레임을 사용하는 HPSS. 종전 HQ v0.2 |
| prominence 비교군 | 14 | 두 HPSS 판단 혼합. 선택하지 않은 실험 |
| **P1++** | 미정 | P1+를 기준으로 이어가는 정교화 연구. 아직 새 성능 주장이 없음 |

고정 식별자는 `p1plus-2026-10-26`이다. 공개 알고리즘 번호 6(P1)은 바꾸지 않았다.
호스트에서 처리 시작 전에 `pvb_set_p1plus_research(handle, 6)`을 호출한다.
연구 플래그는 기본 0이며 JNI/UI에는 연결하지 않았다. `render_p1hq.py`의 기본 이름은
`p1plus`이고 기존 `hq`와 `centered`는 같은 출력의 호환 별칭이다.

이름을 붙이면서 DSP 계수나 처리 규칙을 다시 조정하지 않았다. 최신 main의 Bankstown
저작권 주석을 보존했고, 저장소에서 실행할 수 있도록 도구의 라이브러리 경로와 이름만 정리했다.

## 얻은 것과 남은 것

- 추가 지연 26.667 ms. 48 kHz 엔진 보고 지연 148.750 → 175.417 ms.
- phase-only 대비 짧은 음의 주 배음 윤곽 오차 감소 1.81~11.94 dB, 중앙값 8.19 dB.
  6조건 중 5개의 상대 오차 RMS는 약 13~22%에서 5~9%로 감소했다.
- 약 45 Hz를 포함한 어려운 조건은 101.9% → 82.8%로 여전히 오차가 크다.
  조건마다 음 길이·변조·잡음도 달라 주파수만의 원인으로 단정하지 않는다.
- 위상 문턱 시험의 9~33 dB 개선은 대부분 phase-only의 성과다. P1+의 추가 지연으로
  얻은 해당 지표의 추가 개선 중앙값은 약 0.012 dB다.
- 12개 알려진 혼합 신호의 중간 분리 오차는 5개 개선, 7개 악화했다.
- 실곡 29파일의 87구간을 처리했다. 생성층 RMS 변화는 약 −1.75~+2.20 dB.
  실곡의 출력 차이나 RMS를 음질 점수로 사용하지 않는다.
- 호스트 엔진 회귀 71/71 및 별도 HQ 구현 검사를 통과했다. 폰의 청감·전력·발열 우위를
  확정한 결과가 아니다. 측정 조건들은 후보 선택에 사용되어 미개봉 최종 시험 세트가 아니다.

배음 세기와 추가 지연은 허용하고 비용으로 기록한다. 이전 ±0.3 dB/추가 지연 금지 조건을
이 연구의 자동 탈락 기준으로 다시 사용하지 않는다. 정상 변조·어택·잔향까지 지우는 변화는
오차 감소로 착각하지 않도록 별도 대조군과 함께 평가한다.

근거와 결과 파일: [고정 측정 기록](../research/p1plus/2026-10-26/README.md).
다음 연구: [P1++ 연구 계약](P1PP_RESEARCH.md).

## 저장소에서 실행

Python 3와 `numpy`, `scipy`, `soundfile`이 필요하다. 기록 생성에 사용한 버전은
numpy 2.3.5 / scipy 1.18.1 / soundfile 0.14.0이다. 원본 음악은 저장소에 올리지 않았다.

Linux에서는 기존 호스트 빌드를 사용한다(JDK는 기존 JNI 빌드에 필요).

```sh
tools/pvb-harness/build_host.sh
python3 tools/pvb-harness/render_p1hq.py --input /path/music.flac --output /path/music_P1plus.wav --mode p1plus --peak-target -1
python3 tools/pvb-harness/check_p1hq_primary_envelopes.py --library tools/pvb-harness/build/libpvbcapi.so --report primary-envelopes.json
```

Windows에서는 명시한 Zig 0.16.0으로 빌드한다.

```powershell
python tools/pvb-harness/build_host_windows.py --zig C:/path/zig.exe --out tools/pvb-harness/build
python tools/pvb-harness/render_p1hq.py --input C:/path/music.flac --output C:/path/music_P1plus.wav --mode p1plus --peak-target -1
```

내보낸 WAV의 앞부분은 보고 지연만큼 보상한다. 실시간 지연이 없어지는 것은 아니다.
선택적인 `--peak-target`은 곡 전체에 단 한 번의 재생용 이득을 적용한다.

독립적인 이전 코드와 비교하는 전체 검사에는 별도 대조군 라이브러리가 필요하다.
기존 P1은 커밋 `4331423274665b6c16ca9d438389c289e39b92d4`에서 빌드한다.
phase-only는 같은 커밋에 [보존한 패치](../research/p1plus/2026-10-26/phase-only-control.patch)를
적용해 빌드한다. 예를 들어 저장소 밖의 두 Git worktree에 각각 이 커밋을 체크아웃하고,
phase-only worktree의 루트에서 `git apply /absolute/path/to/phase-only-control.patch`를 실행한다.
Windows 빌더는 `--source-root /path/to/control-checkout`을 지원한다.
대조군을 현재 후보 라이브러리로 대체하여 출력 일치 검사를 통과시키지 않는다.

```sh
python3 tools/pvb-harness/run_p1hq_suite.py --candidate /path/P1plus/library --baseline /path/P1/library --previous /path/phase-only/library --out /path/recheck
```

실곡 검사에는 `--music-folder /path/to/folder`를 여러 번 붙인다. 이전 `run_p1plus_suite.py`는
초기 연구의 역사적 기준을 보존한 도구이며, 현 P1+ 채택 여부를 판정하는 도구가 아니다.
