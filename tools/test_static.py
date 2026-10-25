#!/usr/bin/env python3
"""Static checks that catch what compiling does not (run by CI before the Kotlin build; no Android needed).

Each test is a bug this project shipped or nearly shipped:
  - a reflective call to an Android method that does not exist (compiles, fails on the phone);
  - a foreground service type without its permission, or a permission without a type;
  - a start path that asks for the screen-share consent before checking whether it is needed;
  - a version, notes heading or README that disagree.
"""
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "app/src"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def read(p):
    return (ROOT / p).read_text(encoding="utf-8")


class InterceptServerReflection(unittest.TestCase):
    fixture = read("tools/fixtures/aosp_audiopolicy_api.txt")
    server = read("app/src/main/java/me/timschneeberger/rootlessjamesdsp/capture/InterceptServer.kt")

    def known(self, kind):
        return {m.group(1).split(".")[-1] for m in re.finditer(rf"^{kind}\s+(\S+)", self.fixture, re.M)}

    def test_every_reflective_name_is_in_the_verified_list(self):
        methods = set(re.findall(r'(?:getMethod|getDeclaredMethod)\("(\w+)"', self.server))
        fields = set(re.findall(r'getField\("(\w+)"', self.server))
        self.assertEqual(methods - self.known("method"), set(), "reflective method not verified against the Android source")
        self.assertEqual(fields - self.known("field"), set(), "reflective field not verified against the Android source")

    def test_nothing_calls_a_method_known_not_to_exist(self):
        for m in re.finditer(r"^absent\s+\S+\.(\w+)\s", self.fixture, re.M):
            self.assertNotIn(f'"{m.group(1)}"', self.server, f"{m.group(1)} does not exist")

    def test_excluded_uids_go_through_excludeMixRule_with_match_uid(self):
        self.assertIn('"excludeMixRule"', self.server)
        self.assertIn('"RULE_MATCH_UID"', self.server)
        self.assertNotIn('"RULE_EXCLUDE_UID"', self.server, "addMixRule refuses the exclude flag")


class Manifest(unittest.TestCase):
    root = ET.parse(SRC / "main/AndroidManifest.xml").getroot()

    def test_each_foreground_service_type_has_its_permission(self):
        perms = {p.get(ANDROID + "name") for p in self.root.iter("uses-permission")}
        for svc in self.root.iter("service"):
            types = svc.get(ANDROID + "foregroundServiceType")
            if not types:
                continue
            for t in types.split("|"):
                # camelCase type -> FOREGROUND_SERVICE_UPPER_SNAKE
                perm = "android.permission.FOREGROUND_SERVICE_" + re.sub(r"(?<!^)(?=[A-Z])", "_", t).upper()
                self.assertIn(perm, perms, f"{svc.get(ANDROID + 'name')} declares {t} without {perm}")

    def test_rootless_service_can_start_without_a_screen_share_consent(self):
        svc = next(s for s in self.root.iter("service") if s.get(ANDROID + "name") == ".service.RootlessAudioProcessorService")
        self.assertIn("mediaPlayback", svc.get(ANDROID + "foregroundServiceType").split("|"))


class StartPathOrder(unittest.TestCase):
    """The screen-share consent is asked only after the app has checked it is needed."""
    files = [
        "app/src/general/java/me/timschneeberger/rootlessjamesdsp/home/HomeActivity.kt",
        "app/src/general/java/me/timschneeberger/rootlessjamesdsp/advanced/RnAdvancedActivity.kt",
        "app/src/main/java/me/timschneeberger/rootlessjamesdsp/activity/MainActivity.kt",
        "app/src/main/java/me/timschneeberger/rootlessjamesdsp/activity/EngineLauncherActivity.kt",
    ]

    def test_every_consent_request_comes_after_the_no_consent_check(self):
        for f in self.files:
            s = read(f)
            for m in re.finditer(r"createScreenCaptureIntent\(\)", s):
                before = s[:m.start()]
                fn = before.rfind("fun ") if "fun " in before else before.rfind("override fun onCreate")
                scope = before[fn:] if fn >= 0 else before
                if "onCreate" in scope[:80] or True:
                    self.assertIn("CaptureStart.withoutConsent", scope, f"{f}: consent asked before checking intercept")

    def test_intercept_start_passes_no_projection(self):
        for f in self.files:
            s = read(f)
            self.assertRegex(s, r"CaptureStart\.withoutConsent\(this\)[\s\S]{0,200}RootlessAudioProcessorService\.start\(this, null\)", f)


class Versions(unittest.TestCase):
    def test_general_version_is_the_same_everywhere(self):
        cfg = read("buildSrc/src/main/kotlin/AndroidConfig.kt")
        name = re.search(r'generalVersionName = "([^"]+)"', cfg).group(1)
        code = re.search(r"generalVersionCode = (\d+)", cfg).group(1)
        self.assertIn(f"{name} / {code}", read("RELEASE_GENERAL.md"))
        self.assertIn(f"`{name}`", read("README.md"))
        notes = read("RELEASE_NOTES_GENERAL.md")
        self.assertRegex(notes, re.compile(rf"^## {re.escape(name)}$|^## 다음 버전 \(작업 중\)$", re.M), "notes heading")
        self.assertNotRegex(read("RELEASE_GENERAL.md"), r"general-v0\.9\.0-beta\.(?!%s)" % re.escape(name.split(".")[-1]))


class CaptureStrings(unittest.TestCase):
    def keys(self, lang):
        p = SRC / f"main/res/{lang}/strings_capture.xml"
        return {s.get("name") for s in ET.parse(p).getroot().iter("string")}

    def test_korean_and_english_have_the_same_keys(self):
        self.assertEqual(self.keys("values"), self.keys("values-ko"))


class MotionGuard(unittest.TestCase):
    """tools/check_motion.py actually fails on what it forbids (it was only ever shown to pass)."""

    def run_guard(self, text):
        import importlib.util, tempfile
        spec = importlib.util.spec_from_file_location("check_motion", ROOT / "tools/check_motion.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, text

    def test_script_rejects_each_forbidden_pattern(self):
        import subprocess, tempfile, shutil
        bad = {
            "tween": "val a = tween<Float>(100)",
            "spring": "val a = spring<Float>()",
            "bezier": "val e = CubicBezierEasing(0f,0f,1f,1f)",
            "reduce": "val reduceMotion = true",
            "scale": "Settings.Global.ANIMATOR_DURATION_SCALE",
            "long": "RnMotion.Seed.move<Float>(400)",
        }
        for name, line in bad.items():
            tmp = Path(tempfile.mkdtemp())
            d = tmp / "app/src/general/java/x"
            d.mkdir(parents=True)
            (d / "Screen.kt").write_text("package x\n" + line + "\n")
            (tmp / "tools").mkdir()
            shutil.copy(ROOT / "tools/check_motion.py", tmp / "tools/check_motion.py")
            r = subprocess.run([sys.executable, str(tmp / "tools/check_motion.py")], cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, f"guard missed: {name}")
            shutil.rmtree(tmp)

    def test_script_allows_the_opt_out_and_the_token_file(self):
        import subprocess, tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        d = tmp / "app/src/general/java/x"
        d.mkdir(parents=True)
        (d / "Screen.kt").write_text("package x\nval a = tween<Float>(100) // motion-ok: test\n")
        (tmp / "tools").mkdir()
        shutil.copy(ROOT / "tools/check_motion.py", tmp / "tools/check_motion.py")
        r = subprocess.run([sys.executable, str(tmp / "tools/check_motion.py")], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
