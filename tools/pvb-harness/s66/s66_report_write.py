from pathlib import Path
import json,hashlib,shutil,datetime
import numpy as np
O=Path.home()/'r3a-dev/plan16/s66';R=Path('/mnt/c/Users/ksysh/rootnote-duo');G=R/'gpt-cli'
def read(n):return json.loads((O/n).read_text())
def fmt(v,d=3):return 'N/A' if v is None else f'{v:+.{d}f}'
def main():
 s=read('SUMMARY.json');assert s['complete'];model=read('PCM_PHONE.json');wf=read('WAVEFORM_CLOSURE_v2.json');qa=read('FINAL_QA.json');detail=read('DETAILED_DEV3.json');commit=read('LOCAL_COMMIT.json')['commit'];n=s['n']
 def cell(name,ctx='digital',ref='B'):return next(v for v in s['summary'] if v['variant']==name and v['context']==ctx and v['reference']==ref)
 def val(name,ctx='digital',ref='B'):return fmt(cell(name,ctx,ref)['weak_db']['median'])
 valid=cell('B','digital','P1')['weak_db']['n'];control=wf['controls'];pk={v['variant']:v for v in s['peaks']}
 lines=[
 f'1. 노출 DEV {n}곡을 P1/B/T/C1/C2/C3로 실제 인과 렌더했으며, weak25 유효 {valid}곡·지지 없는 {n-valid}곡은 N/A로 남겼다.',
 f'2. 두 기존 녹음을 제자리에서 읽어 대역 정적곡선과 공통 이력 상태 하나의 PCM_PHONE을 만들었다(선택 attack100ms/release1.2s).',
 f'3. 정정 후에도 모델은 사전 문턱을 통과하지 못했다: 20cm 150–300Hz 중앙 절대오차{wf["errors20cm"][1]["median_abs_db"]:.2f}dB, +4 H/L 오차{control[0]["error_db"]:+.2f}/{control[1]["error_db"]:+.2f}dB다.',
 f'4. B/P1 약배음 합출력 중앙은 digital {val("B","digital","P1")}dB, 모델20H {val("B","phone20H","P1")}dB이며 폰 실측 재확인이 아니다.',
 f'5. C1/B 약배음 중앙은 digital {val("C1")}dB·모델20H {val("C1","phone20H")}dB; 정답/대역 비는 늘지만 절대 약배음 이득이 분명하지 않다.',
 f'6. C2/B 약배음 중앙은 digital {val("C2")}dB·모델20H {val("C2","phone20H")}dB로, 일부 변조·잡음 감소와 증량 손실이 섞인다.',
 f'7. C3/B 약배음 중앙은 digital {val("C3")}dB·모델20H {val("C3","phone20H")}dB; 유리한 대역 선택의 근거도 약하다.',
 f'8. 세 후보 모두 {n}곡 TP8≤P1+0.5dB이며 최악은 C1 {pk["C1"]["tp_delta_P1_db"]["max"]:+.3f}, C2 {pk["C2"]["tp_delta_P1_db"]["max"]:+.3f}, C3 {pk["C3"]["tp_delta_P1_db"]["max"]:+.3f}dB다.',
 '9. 기본 OFF 비트 동일·블록/인과성·같은7140샘플 지연을 확인했고, 15cm용247초 PCM24·map·한국어 방법·분석기를 준비만 했다.',
 '10. 이 세 후보의 다음 단계 채택은 없음이다. 새 폰 측정에서 레벨곡선·회복·대역 순위를 먼저 확인하고 B를 기준으로 유지한다.',
 '',
 '범위와 판정',
 f'기준 worktree ~/r3-s66, branch research/s66-20261102, base9d408fb, 로컬 코드 commit {commit}. 작업 ~/r3a-dev/plan16/s66/.',
 '기존50cm raw_153239·20cm raw_155636의48kHz mono 방 녹음과 실제s59 continuous PCM을 사용했다. 방·스테레오 합성·마이크 응답까지 포함하며 절대SPL/독립 폰 캡슐 모델이 아니다.',
 '두 affine sync는 기존 s59_analysis/analysis.json 그대로다. room recording 및 사용자 원음 복사/커밋, validation/test 열람·열거, confirm 자료 실행, T7 rootnote-data 접근, CORE 편집, push, 앱 빌드는 없다.',
 'REGISTRATION.md/json/sha256을 후보 결과 전에 동결했다. repeat2 전체·DEV00030 전체·+4 전체를 fit에서 제외했고, 나머지repeat1의 두 거리/H,L를 fit했다. 같은 음악 반복이므로 독립 새 곡 검증은 아니다.',
 '원등록 모델 V1은 겹치는 band 합성의10–12dB waveform 오차로 실패했다. V1 후보5곡·모델·원문을 v1_preserved에 보존했다.',
 'MODEL_CORRECTION_v2_REGISTRATION은 disjoint STFT로 정정했고, v2_uncensored_preserved에 부분2곡과 실패 검증을 남겼다. 이후5개밖에 없는 <150Hz fit의 외삽을 배제한 v2.1 도메인 정정도 별도 등록했다.',
 '원등록 통과로 소급하지 않는다. 최종 phone 점수는 전부 정정 후 탐색 결과다. native 후보3개와 파라미터·C3의원래 high-half 선택은 바꾸지 않았다.',
 '자체 구현의 scalar/vector dB 오류와 weak 지지 전곡 가정도 실패 시점·원본/해시와 함께 정정했다. 기존 유효 digital 행은 같은 PCM/지표인지 대조했다. 세부 이력은 CORRECTIONS/NA_CORRECTION/PREFETCH_*에 있다.',
 '',
 'PCM_PHONE와 검증',
 '150–300/300–600/600–3000/3000Hz+의 정적 dB 곡선과 거리별 절편, 공통 이력 h만 사용한다. <150Hz는 식별 불가로 평가기에서 사실상 제외하며 기본음 보존·이 대역 전달은 N/A다.',
 '이전10ms band power x에 대해 g=a+(s_low−1)min(x+30,0)+(s_high−1)max(x+30,0)−c·h, h는 max(total_dB+35,0)의 비대칭 평활이다. 기울기0.1–1.2, c0–2로 제한했다.',
 '2048 Hann/480 hop의 겹치지 않는 주파수 bin에 g를 적용하고 정규화 WOLA로 복원한다. 이 offline 평가 창은 포락선을 약21ms 흐릴 수 있다. native 후보의 추가 지연은0이다.',
 '공통 이력의 선택100ms/1.2s는 음악+짧은probe의 현상론적 fit이며 독립 하드웨어 시정수 추정이 아니다. 후보30초 점수는 조용한 초기 상태·공통 설정에서의 시나리오다.',
 '| 대역 Hz | 정적 low/high 기울기 | history c | 20cm holdout 중앙절대/p90 dB |',
 '|---|---:|---:|---:|']
 for j in range(1,5):
  b=model['bands'][j];e=wf['errors20cm'][j];lines.append(f'| {b["band_hz"][0]}–{b["band_hz"][1]} | {b["slope_low"]:.3f}/{b["slope_high"]:.3f} | {b["history_coefficient"]:.3f} | {e["median_abs_db"]:.2f}/{e["p90_abs_db"]:.2f} |')
 lines+=['문턱은 주 대역 중앙절대≤2dB/p90≤5dB, +4 H,L 각각오차≤0.75dB, 음악 H−L≤1.5dB, 1kHz probe H−L≤1dB·부호 음수다. 원등록과20cm 중심 정정 판정 모두 실패다.',
 '| 20cm 대조 | 예측 dB | 관측 dB | 예측−관측 dB |', '|---|---:|---:|---:|']
 for z in control:lines.append(f'| {z["kind"]} {z["level"]} | {z["predicted_db"]:+.3f} | {z["observed_db"]:+.3f} | {z["error_db"]:+.3f} |')
 lines += [f'실제 복원파형으로 재검증했다. 정규화 unity 복원 최대오차{wf["unity_reconstruction_max_error"]:.2e}; 음악 1–4Hz log-gain 잔차 RMS 중앙{wf["median_residual_1_4_rms_db"]:.2f}dB다. 고정 방 응답/스테레오와 폰 동특성은 완전히 분리되지 않는다.',
 '특히150–300Hz와 작은 재생 L의 +4 감도가 실패하며 H/L +4 감도 순서도 거꾸로 예측한다. 50cm 저대역은 SNR 지지가 약하다. 작은 후보 차이를 폰 개선·순위로 확정할 수 없다.',
 '',
 '후보와 효능',
 '모든 후보는 B 위의 startup-only host research 매개변수(기본 mode0 OFF)다. C1=dry−0.75dB/layer+0.75dB, C2=layer+0.75dB·fast10/slow400ms 초과3dB burst를 최대3dB 억제(5/200ms gain), C3=LP300 보완분할 layer high+1/low−1dB다.',
 'T는 기존 B의 A-release20ms(기준100ms) 진단 대조이며 네 번째 새 후보가 아니다. C3 선택은 V1의 미세한 static slope차에 기대었고 정정 후에는 유리한 쪽도 바뀌므로 근거가 특히 약하다.',
 '같은 input·공통 engine 설정에서 source-aligned30초 지표를 계산했다. TP8은 startup/flush를 포함한 실제 native 출력 전체다. offline peak/음량 맞춤이나 곡별 gain 조절은 하지 않았다.',
 f'아래는 유효 {valid}곡의 paired-song 중앙 ΔdB다. weak25는 기존 dry 정답배음/기본음 비 하위25% 마스크의 합출력이며 생성층만의 세기가 아니다. 비율은 정답 Q/150–600Hz 전체 전력이다.',
 '| 변형 | digital/P1 weak | digital/B weak | phone20H/P1 weak | phone20H/B weak | phone20L/B weak | digital/B 비율 |',
 '|---|---:|---:|---:|---:|---:|---:|']
 for name in ['B','T','C1','C2','C3']:
  if name=='B':lines.append(f'| B | {val(name,"digital","P1")} | 0 | {val(name,"phone20H","P1")} | 0 | 0 | 0 |')
  else:lines.append(f'| {name} | {val(name,"digital","P1")} | {val(name)} | {val(name,"phone20H","P1")} | {val(name,"phone20H")} | {val(name,"phone20L")} | {fmt(cell(name)["ratio_db"]["median"])} |')
 lines+=['| 후보/B | digital weak 중앙 bootstrap95% dB | phone20H weak 중앙 bootstrap95% dB | >0.5dB weak 손실곡 digital/H |', '|---|---:|---:|---:|']
 for name in ['C1','C2','C3']:
  d=cell(name);h=cell(name,'phone20H');di=d['weak_median_bootstrap95'];hi=h['weak_median_bootstrap95'];lines.append(f'| {name} | [{di[0]:+.3f},{di[1]:+.3f}] | [{hi[0]:+.3f},{hi[1]:+.3f}] | {d["weak_loss_gt05_count"]}/{h["weak_loss_gt05_count"]} |')
 lines+=['10,000회 곡 단위 paired median bootstrap(고정 seed6602)은 노출 DEV 내부 변동이다. mic 실측 신뢰구간·새 확인 시험이 아니다.',
 '',
 '들리는 네 해악과 혼재 손익',
 '틀린 음=고정 P1 family의 합출력 오배음 전력 및 N1 wrong/correct, N2=고정 MIDI 지속 구간 합출력의 정규화1–4/4–10/10–30Hz envelope 대리다. 원음의 음악적 AM도 포함하므로 실제 오음률·쿠쿠쿵 발생률이 아니다.',
 '전곡 공백/소실은 MIDI 지지에서 bass150–600Hz가 P1보다−12dB·30ms 이상 약한 대리(−6dB 보조), 어택은 local/fixed-P1 10% rise다. 정답 배음 자체의 bank 공백은 DEV3 추가 진단으로만 확인했다.',
 '따라서 원등록의 전곡 정답배음 공백 표현에 해당하는 직접 증거는 DEV3로 제한한다. broadband 공백이0이라고 전곡 정답 음 소실이0이라고 말하지 않는다. local rise 역시 실제 음 시작 지연의 검증된 척도는 아니다.',
 '아래는 B 대비 digital 중앙이다. N2는1–4Hz이고 나머지 두 대역·최악곡·지지수는 SUMMARY/PAIRED_DEV에 있다. 손익 flag는 family/N1/N2≥1dB, gap/loss≥1%p, local어택 중앙≥10ms/p95≥20ms의 탐색 표시다.',
 '| 후보 | 오배음 dB | N1 dB | N2 1–4 dB | gap %p | loss %p | local어택 ms | flag곡 digital/20H/20L |', '|---|---:|---:|---:|---:|---:|---:|---:|']
 for name in ['C1','C2','C3']:
  d=cell(name);lines.append(f'| {name} | {fmt(d["family_power_db"]["median"])} | {fmt(d["N1_mixed_db_delta"]["median"])} | {fmt(d["N2_bands_db"][0]["median"])} | {fmt(d["gap_pp_delta"]["median"])} | {fmt(d["loss_pp_delta"]["median"])} | {fmt(d["attack_local_median_ms"]["median"],1)} | {d["harm_flag_song_count"]}/{cell(name,"phone20H")["harm_flag_song_count"]}/{cell(name,"phone20L")["harm_flag_song_count"]} |')
 for name in ['C1','C2','C3']:
  d=cell(name);lines.append(f'{name} 진단: B 대비 RMS {fmt(d["rms_dbfs_delta"]["median"])}dB, crest {fmt(d["crest_db_delta"]["median"])}dB, body {fmt(d["body_power_db"]["median"])}dB; TP8/P1 최악{pk[name]["tp_delta_P1_db"]["max"]:+.3f}dB. body/crest/limiter는 독립 거부권이 아니다.')
 lines += ['C1의 digital flag8곡은 local어택7곡(곡내 p95 최악39.4ms)과 Track00018의N2 대리다. 모델 H/L의flag0을 폰에서 해악이 사라졌다는 증거로 쓰지 않는다.',
 'DEV3 legacy 층 N2의 C1/B는 Track00001/00030 −0.571/−0.015dB, C2/B는 +0.526/+0.227dB, C3/B는 +0.010/+0.101dB다(Track00016 N/A). C2의 총합1–4Hz 대리 감소를 층 쿠쿠쿵 개선으로 바꿔 말할 수 없다.',
 'DEV3 정답배음 bank에서는 세 후보 모두 digital·model20H/L·50H의 P1 대비−12dB/30ms 소실0건이었다. 이는3곡 대리의 제한된 지지이며 실제 폰·전곡 음 소실 부재의 증명은 아니다.',
 '공통 해석: C1의 비율·피크 여유 이득은 dry를 깎는 비용과 함께 생긴다. C2의 burst 억제는 일부 총합 변조/오배음 감소와 정상 약배음 손실, legacy 층 N2 증가가 함께 있다. C3는 배분 방향 불확실성과 작은 약배음 손실 때문에 순이득이 입증되지 않는다.',
 'flag 하나로 기각하지 않았으며 개선 폭·악화 폭·곡 지지를 함께 보았다. 다만 세 후보 모두 B 대비 우연이 아닌 약배음 증량이 분명하지 않고 모델 오차보다 작아, 이번 혼재 손익은 전진 채택을 지지하지 않는다.',
 '',
 '검증·측정 키트·결정',
 'V0 P1/B48kHz, OFF44.1kHz, block37/256 및 동일 prefix 이후 입력변경 인과성, startup 지연7140샘플, serial/prefetch PCM bit동일을 확인했다. host setter 전처리 guard 수정도 평가 바이너리와 최종 바이너리 PCM 동일·native nonresearch syntax로 확인했다.',
 'DETAILED_DEV3에는 legacy layer N1/N2/endpoint와 digital·phone20H/L·50H의정답 k2–8±25Hz bank 공백이 있다. 이 legacy/합출력/phone 대리를 서로 같은 지표로 치환하지 않았다.',
 '모든 room recording와 continuous 입력 전체 SHA256, DEV mix SHA256 불변을 다시 확인했다. 오디오는 메모리에서 처리했으며 저장한 WAV는 승인된 synthetic 측정 파일 하나뿐이다. 실행 최대2 jobs·총6 threads, BLAS1이다.',
 '키트: C:\\Users\\ksysh\\rootnote-duo\\listen\\s66\\s66_phone_characterisation_15cm.wav (247초,48kHz stereo PCM24, peak−6dBFS). 80/200/400/1000/4000Hz 단계·burst, loud/quiet 뒤5초250/1000Hz probe, 동일/+4 대조와12개chirp가 있다.',
 '같은 폴더의 segment_map.json·측정 방법.md·analyze_s66.py가 측정/재사용 계약이다. 분석기는 s59 affine 동기,40ms joint tone fit/20ms hop, noise99+10dB 지지, plateau/+4/동일 차 및 회복곡선 fit을 낸다. 디지털 fixture의12/12 sync·0 clipping·동일0/+4를 확인했다. 실제15cm 녹음은 아직 없다.',
 '결정: 후보 채택 없음, B 유지. C1은 비율 배분의 탐색 가설로만 남기고 C2/C3를 다음 투자 우선으로 올리지 않는다. T는 별도 기존 대조이며 이번 신규 후보 채택이 아니다.',
 '다음15cm 측정은 (1) 각 대역 H/L static 감도의 순서와 +4 전달, (2) loud/quiet 뒤 동일1kHz의억제량과5초 회복, (3)150–300 대300–600 압축 순위의반복성, (4)동일 대조 변동보다 큰 배음비/약배음 증가를 확인해야 한다. 이후 후보를 측정하고 판정용 청감은 블라인드로 한다.',
 '재현: 보존 원등록/정정 이력 확인 → s66_setup/engine → s66_phone 및 v2 정정·도메인 제한 → s66_validate_v2 → s66_eval --rest --shards 2 --shard 0/1 → s66_summary/detail → s66_qa/kit 분석 → s66_report_write. 정확한 CLI와 버전 순서는 worktree tools/pvb-harness/s66/README.md에 있다.',
 '주 파일: REGISTRATION*, MODEL_CORRECTION*/MODEL_DOMAIN*, PCM_PHONE, MODEL_VALIDATION, WAVEFORM_CLOSURE_v2, results87개, SUMMARY/PAIRED_DEV, DETAILED_DEV3, V0_AND_CAUSALITY, FINAL_QA, INPUTS, KIT_QA, LOCAL_COMMIT. 미사용·실패 버전은 삭제하지 않았다.'
 ]
 assert len(lines)-11<=120,(len(lines),len(lines)-11)
 text='\n'.join(lines)+'\n';(O/'s66_report.md').write_text(text,encoding='utf-8');(G/'s66_report.md').write_text(text,encoding='utf-8')
 section='## 66. 폰 압축 인지 출력 배분: DEV87 탐색과15cm 특성 측정 준비\n\n'+text
 (O/'SECTION_s66_draft.md').write_text(section,encoding='utf-8');(G/'SECTION_s66_draft.md').write_text(section,encoding='utf-8')
 files=[O/'s66_report.md',G/'s66_report.md',O/'SECTION_s66_draft.md',G/'SECTION_s66_draft.md',R/'listen/s66/측정 방법.md'];out=[]
 for p in files:
  raw=p.read_bytes();assert not raw.startswith(b'\xef\xbb\xbf');t=raw.decode('utf-8');line=next(v for v in t.splitlines() if any('\uac00'<=c<='\ud7a3' for c in v));out.append(dict(path=str(p),korean_reread=line,sha256=hashlib.sha256(raw).hexdigest(),lines=len(t.splitlines())))
 (O/'REPORT_QA.json').write_text(json.dumps(dict(summary_lines=10,body_lines=len(lines)-11,files=out),ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('report lines',len(lines),'body',len(lines)-11);print(out[0]['korean_reread'])
if __name__=='__main__':main()
