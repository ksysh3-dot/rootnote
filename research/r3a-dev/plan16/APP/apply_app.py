import os
os.chdir(os.path.expanduser('~/r3-app'))
def rw(p, f):
    s = open(p, encoding='utf-8', newline='').read()
    t = f(s)
    assert t != s, p
    open(p, 'w', encoding='utf-8', newline='').write(t)

NEW = ('        Model("resultant_core_v15", RESULTANT, "Resultant 코어 v1.5 (실험)", "P1의 음 추적은 그대로 두고, 배음층을 음마다 이어지는 새 방식으로 만듭니다. '
       '음이 다시 칠 때 층이 끊기거나 깜빡이던 것이 크게 줄었습니다(연구 측정). 어택이 약 20 ms 늦고, 베이스가 없는 곳에서 낮은 소리가 조금 더 날 수 있습니다. 지연은 P1과 같습니다."),')

def models(s):
    nl = '\r\n' if '\r\n' in s else '\n'
    s = s.replace('    const val P1_C1 = 14' + nl, '    const val P1_C1 = 14' + nl + '    const val RESULTANT = 15' + nl, 1)
    lines = s.split(nl)
    i = [k for k, l in enumerate(lines) if l.startswith('        Model(P1_KEY, P1,')][0]
    lines.insert(i + 1, NEW)
    return nl.join(lines)
rw('app/src/main/java/me/timschneeberger/rootlessjamesdsp/pvb/PvbModels.kt', models)
rw('app/src/main/cpp/libpvb/pvb_vb.h', lambda s: s.replace('(host research, not an app model)', '(experimental app model 15, defaults of pvb_resultant.h; research params only via the host API)'))
rw('tools/pvb-harness/jvm/Alpha2JniTest.kt', lambda s: s.replace('size == 11', 'size == 12').replace('eleven selectable', 'twelve selectable').replace('P1+C1 ID14)', 'P1+C1 ID14, Resultant v1.5 ID15)'))
rw('tools/pvb-harness/jvm/Alpha3SettingsTest.kt', lambda s: s.replace('P1 + C1 (14, research branch), P1+', 'P1 + C1 (14, research branch), Resultant core v1.5 (15, experimental), P1+').replace('listOf(6, 14, 11,', 'listOf(6, 15, 14, 11,').replace('distinct().size == 11', 'distinct().size == 12'))
