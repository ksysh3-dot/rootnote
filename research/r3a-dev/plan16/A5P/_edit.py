import re
from pathlib import Path
p = Path.home() / 'r3a-dev/plan16/A5P/oracle_p.py'
t = p.read_text()
t = t.replace("from scipy.signal import butter, sosfiltfilt\n", "from scipy.signal import butter, sosfiltfilt, sosfilt, resample_poly\n")
t = t.replace("SOS_LO = butter(4, [20, 150], 'bandpass', fs=FSC, output='sos'); SOS_MID = butter(4, [150, 600], 'bandpass', fs=FSC, output='sos')\n",
 "OUT_SOS = np.array([[0.6620158372026176, -1.3240316744052352, 0.6620158372026176, 1.0, -1.4796742169311934, 0.5558215432824889],\n"
 "                    [1.0, -2.0, 1.0, 1.0, -1.7009643319435257, 0.7884997398152979],\n"
 "                    [0.20657208382614792, 0.41314416765229584, 0.20657208382614792, 1.0, -0.3695273773512414, 0.19581571265583306]])   # vbt::kOutSos (output filter, 48 kHz)\n\n\n"
 "def to_layer(y3k):\n    \"\"\"3 kHz core signal -> 48 kHz (x16 polyphase) -> engine output filter\"\"\"\n    return sosfilt(OUT_SOS, resample_poly(y3k, 16, 1))\n")
t = t.replace("        yl = sosfiltfilt(SOS_LO, y); ym = sosfiltfilt(SOS_MID, y)\n", "        y48 = to_layer(y); yl = sosfiltfilt(P.SOS_LO, y48); ym = sosfiltfilt(P.SOS_MID, y48)\n")
t = t.replace("            n0, n1 = ih[sel.min()], ih[sel.max()] + 16\n", "            n0, n1 = 16 * ih[sel.min()], 16 * (ih[sel.max()] + 16)\n")
t = t.replace("(('raw', 'raw', 1), ('th5', 'th', 5), ('th9', 'th', 9), ('th25', 'th', 25), ('tp9', 'tp', 9), ('tp25', 'tp', 25))", "(('raw', 'raw', 1), ('th3', 'th', 3), ('th5', 'th', 5), ('th9', 'th', 9), ('th15', 'th', 15), ('tp9', 'tp', 9))")
t = t.replace("Band energies of the 7 user windows", "The rebuilt layer is upsampled x16 and passed through the engine output filter (vbt::kOutSos) before the 20-150 / 150-600 Hz zero-phase bands, as the rendered layer is. Band energies of the 7 user windows")
p.write_text(t)
