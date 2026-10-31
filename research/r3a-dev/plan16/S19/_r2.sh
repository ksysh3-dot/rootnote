cd ~/r3a-dev/plan16/S19
source ~/venv-rootnote/bin/activate
mkdir -p cache_v1; mv cache/* cache_v1/ 2>/dev/null
sed -i "s/'a_2', 'a_3'\]/'a_2', 'a_3', 'theta_hat', 'psi_2', 'psi_3']/" s19_render.py
grep -n "^KEEP" s19_render.py
NP=12 nohup python s19_render.py b0p0,b3p2,f4 > render2.log 2>&1 &
echo ok