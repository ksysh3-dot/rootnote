from pathlib import Path
p = Path('/home/ksysh/r3a-dev/plan16/V16A/diag35.py'); t = p.read_text()
a = "int(t['hop'][h, 0]) + off"
assert t.count(a) == 2
t = t.replace(a, "(int(t['hop'][h, 0]) - 383) // 16 + 1 + off")
t = t.replace('for off in (-1, 0, 1):', 'for off in (0, -1, 1):')
p.write_text(t)
