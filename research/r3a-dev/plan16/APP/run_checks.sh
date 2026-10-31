source ~/venv-rootnote/bin/activate
cd ~/r3-app
sed -i 's/lat = \[getattr.*/lat = e.latency()/' ~/r3a-dev/plan16/APP/chk15.py
python ~/r3a-dev/plan16/APP/chk15.py 2>&1 | tail -6
export OPENBLAS_NUM_THREADS=1
echo == test_engine; python tools/pvb-harness/test_engine.py 2>&1 | tail -8; echo rc=$?
echo == alpha2_profiles; python tools/pvb-harness/test_alpha2_profiles.py --lib tools/pvb-harness/build/libpvbcapi.so --report /tmp/a2.json 2>&1 | tail -5
echo == track_protection; g++ -std=c++17 -O2 -Wall -Wextra -Werror -Iapp/src/main/cpp/libpvb tools/pvb-harness/vb_quality/test_track_protection.cpp -o /tmp/pvb-track-protection && /tmp/pvb-track-protection | tail -3
echo == devmode; python tools/pvb-harness/test_devmode.py --baseline-ref 65c0086f01caaeffc8fdea1614560076f9a860cd --report /tmp/dm.json 2>&1 | tail -5
echo == experimental; python tools/pvb-harness/test_experimental.py --baseline-ref 9978f145317183527b15f83d91fe9c6de748ae14 --report /tmp/ex.json 2>&1 | tail -5
