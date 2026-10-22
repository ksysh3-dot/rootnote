# 실험실 (개발자 모드 안쪽) 계획과 문구

개발자 모드가 main에 들어간 뒤 별도 작업으로 붙인다. 문체와 근거 표시는 `docs/DESIGN.md`, `docs/DEVMODE_COPY.md`를 따른다.

## 들어가는 길

개발자 모드 설정 맨 아래 "실험실" → 두 번째 동의. 안의 항목은 모두 기본 꺼짐. 귀 보호 출력 제한은 여기서도 끌 수 없다.

## 동의 문구

**제목:** 실험실을 열까요?

**본문:**
- 이 기능들은 개발 중 시험에서 효과가 없었거나 오히려 나빴던 것들이에요.
- 다만 시험은 한 사람이 한 기기(Galaxy S26 Ultra)로 들은 결과라, 사람과 기기에 따라 실제 체감은 다를 수 있어요. 개발자에게는 차이가 없었어도, 누군가에게는 더 좋게 들릴 수 있어요.
- 항목마다 개발 중 시험 결과를 그대로 적어 두었어요. 직접 들어 보고 판단해 주세요.
- 둘 이상 켜면 시험하지 않은 조합이 돼요. 소리가 깨지거나 커질 수 있고, 그 결과는 책임지지 않아요.
- 좋게 들렸다면 공유 코드와 함께 GitHub Issues로 알려 주세요. 다음 버전의 기본값을 정하는 데 도움이 돼요.

**버튼:** 취소 / 알겠어요, 열기

(EN) Open the lab? These features showed no benefit, or did worse, in our tests. But those tests were one listener on one phone (Galaxy S26 Ultra), so what you hear may differ — something that made no difference for the developer may sound better to you. Each item lists our test result as it was. Turning on more than one makes an untested combination; sound may break up or get louder, at your own risk. If something sounds better to you, please share your code on GitHub Issues — it helps choose future defaults.

## 근거 표시 추가

| 표시 | 뜻 |
|---|---|
| 시험 결과 | Rootnote 개발 중 청취 시험 결과(차수와 결론). 예: "16차: 과함·노이즈" |

## 항목

### ① 엔진에 이미 있음 (꺼내기만)
- 예전 모델: 기준형(24 dB/oct), 세부 추적 D2, 변조 추적 J2, 연속 합성, 연속 합성·위상 보정, 12 dB/oct, 적응형 12/24
- 배음 6~8차 비중

### ② 오프라인 시제품뿐 (실시간 이식 필요, 이식 쉬운 순서)
1. 서브 집중 (생성기 입력 저역 셸프) — 15b차: 차이 미미
2. 저역 대체 (원음 150 Hz 아래 제거 + 층) — 16·17차: +0은 통과, 18차: EQ만보다 킥이 흐림
3. 고차 배음 추가 9~16차, 위쪽 배음 올리기 +12/+24 dB/oct — 14차: 400 Hz 위는 차이 없음, +24는 거울미로 노이즈
4. 구간 자동 세기 (+3~+6) — 20차: 고정과 거의 같음(미세)
5. 지속 (층 꼬리 유지) — 15b차: 서브 집중과 구분 어려움. 킥 꼬리가 길어질 수 있음
6. 옥타브 아래 — 15b차 거울미로 '그나마', 16차: 과함·노이즈, Mirage 쿠쿵

각 항목 설명에는 "실시간판은 오프라인 시험과 처리 방식이 달라 같은 소리가 아닐 수 있어요"를 붙인다(②만).

## 공유 코드

실험실 항목이 하나라도 켜져 있으면 코드에 표시(예: RN1L-…)를 넣고, 불러올 때 "실험실 항목이 들어 있어요" 확인을 받는다.
