#!/usr/bin/env python3
"""Motion guard for the general build's Compose screens (docs/DESIGN.md 6, "한 곳에서만").

Every motion spec is defined in app/src/general/java/.../ui/RnMotion.kt. Screen files name the kind of change
(RnMotion.Seed.color(), RnMotion.Apple.thumb(), ...) and pass it through rn(...); they never build a spec themselves.
This script fails (exit 1) when a general-build Kotlin file outside RnMotion.kt

  - calls tween( / spring( / keyframes( / infiniteRepeatable( / CubicBezierEasing(, or names a stock easing
    (LinearEasing, FastOutSlowInEasing, LinearOutSlowInEasing, FastOutLinearInEasing, EaseIn..., EaseOut...)
  - reads the system animation setting itself (ANIMATOR_DURATION_SCALE, animationsOff( ), or keeps its own
    reduce-motion flag (LocalReduceMotion, LocalDevReduceMotion, a reduceMotion parameter or field)
  - asks for a Seed move / enter / exit longer than 300 ms

A line can opt out with a trailing "// motion-ok: <why>" (use it for something that is not interface motion).
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "app" / "src" / "general"
ALLOWED = {"RnMotion.kt"}
MAX_MS = 300

RULES = [
    (re.compile(r"\b(tween|spring|keyframes|infiniteRepeatable)\s*[<(]"), "build motion specs only in ui/RnMotion.kt"),
    (re.compile(r"\bCubicBezierEasing\s*\("), "curves belong to ui/RnMotion.kt"),
    (re.compile(r"\b(LinearEasing|FastOutSlowInEasing|LinearOutSlowInEasing|FastOutLinearInEasing|EaseIn\w*|EaseOut\w*)\b"),
     "use RnMotion.Seed / RnMotion.Apple / RnMotion.clock"),
    (re.compile(r"ANIMATOR_DURATION_SCALE|\banimationsOff\s*\("), "the animation setting is read once, in ui/RnMotion.kt"),
    (re.compile(r"\b(LocalReduceMotion|LocalDevReduceMotion)\b|\breduceMotion\b"), "use LocalRnReduceMotion (ui/RnMotion.kt)"),
]
LONG = re.compile(r"\bSeed\.(?:move|enter|exit)\(\s*(?:ms\s*=\s*)?(\d+)")
NUMERIC_CROSS = re.compile(r"\bcrossFade\(\s*(\d+)")


def main() -> int:
    bad = []
    files = sorted(p for p in SRC.rglob("*.kt") if p.name not in ALLOWED)
    for path in files:
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//")[0] if "motion-ok" not in line else ""
            if "motion-ok" in line or line.lstrip().startswith(("*", "/*")) or line.lstrip().startswith("import "):
                continue
            for rx, why in RULES:
                if rx.search(code):
                    bad.append(f"{path.relative_to(ROOT)}:{no}: {why}: {line.strip()}")
            for rx in (LONG, NUMERIC_CROSS):
                for m in rx.finditer(code):
                    if int(m.group(1)) > MAX_MS:
                        bad.append(f"{path.relative_to(ROOT)}:{no}: longer than {MAX_MS} ms: {line.strip()}")
    if bad:
        print("Motion rules broken (docs/DESIGN.md 6):")
        print("\n".join(bad))
        return 1
    print(f"Motion rules hold in {len(files)} general-build files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
