from pathlib import Path
import json,subprocess,shutil
H=Path.home();P=H/'r3a-dev/plan16';O=P/'s66';W=H/'r3-s66';C=W/'app/src/main/cpp/libpvb'
def rep(p,a,b):
 s=p.read_text();assert s.count(a)==1,(p,a);p.write_text(s.replace(a,b),encoding='utf-8')
if not (C/'pvb_allocation66.h').exists():
 (C/'pvb_allocation66.h').write_text('''#pragma once
#include <cmath>
#include <algorithm>
namespace pvb {
// Startup-only host research parameters. Mode0 executes no audio arithmetic.
// This allocator has no signal buffer or added latency. Native A/TP8 certificate
// and limiter see the allocated components, preserving their existing schedule.
class Allocation66 {
 int mode_=0; bool high_=true; double low_[2]={},fast_=0.,slow_=0.,gain_=1.;
public:
 bool set(int mode,bool high) {if(mode<0||mode>3)return false;mode_=mode;high_=high;reset();return true;}
 void reset() {low_[0]=low_[1]=fast_=slow_=0.;gain_=1.;}
 int mode() const {return mode_;}
 void tick(double& dL,double& dR,double& lL,double& lR,double fs) {
  if(!mode_)return;
  constexpr double up=.0901844923851276+1.; // +0.75dB
  if(mode_==1) {const double down=1./up;dL*=down;dR*=down;lL*=up;lR*=up;return;}
  if(mode_==2) {
   const double p=.5*(lL*lL+lR*lR);
   const double af=1.-std::exp(-1./(.010*fs)),as=1.-std::exp(-1./(.400*fs));
   fast_+=af*(p-fast_);slow_+=as*(p-slow_);
   const double excess=10.*std::log10(std::max(fast_,1e-30)/std::max(slow_,1e-30))-3.;
   const double attenuation=std::max(0.,std::min(3.,excess));
   const double target=std::pow(10.,-attenuation/20.);
   const double ag=1.-std::exp(-1./((target<gain_?.005:.200)*fs));
   gain_+=ag*(target-gain_);lL*=up*gain_;lR*=up*gain_;return;
  }
  // Causal one-pole LP300. Complement is exact before allocation.
  const double a=1.-std::exp(-2.*3.14159265358979323846*300./fs);
  low_[0]+=a*(lL-low_[0]);low_[1]+=a*(lR-low_[1]);
  const double gu=std::pow(10.,1./20.),gd=1./gu;
  const double gl=high_?gd:gu,gh=high_?gu:gd;
  lL=gl*low_[0]+gh*(lL-low_[0]);lR=gl*low_[1]+gh*(lR-low_[1]);
 }
};
}
''',encoding='utf-8')
 p=C/'pvb_engine.h'
 rep(p,'#pragma once','#pragma once\n#ifdef PVB_HOST_RESEARCH\n#include "pvb_allocation66.h"\n#endif')
 rep(p,'    bool setP1WrongNoteResearch(unsigned flags)', '''#ifdef PVB_HOST_RESEARCH
    // Configure before processing; mode0 preserves P1/B arithmetic exactly.
    bool setAllocation66(int mode,bool high,int recovery) {
        if(sr_!=48000 || (recovery!=100 && recovery!=20))return false;
        if(!allocation66_.set(mode,high))return false;
        recovery66_=recovery;return true;
    }
#endif
    bool setP1WrongNoteResearch(unsigned flags)''')
 rep(p,'    int dryLowCutMode_ = 0;', '''#ifdef PVB_HOST_RESEARCH
    Allocation66 allocation66_;
    int recovery66_=100;
#endif
    int dryLowCutMode_ = 0;''')
 p=C/'pvb_layer_peak42.h';rep(p,' void reset() {',' bool setRecovery66(int ms) {if(ms!=20 && ms!=100)return false;releaseCoef_=1.-std::exp(-1./(.001*ms*fs_));return true;}\n void reset() {')
 p=C/'pvb_engine.cpp'
 rep(p,'    configureDryLowCut();boundedPeak50_.reset();','''#ifdef PVB_HOST_RESEARCH
    if(on && recovery66_!=100)layerPeak42_.setRecovery66(recovery66_);
#endif
    configureDryLowCut();boundedPeak50_.reset();''')
 rep(p,'    boundedPeak50_.reset();\n    lim_.reset();','''    boundedPeak50_.reset();
#ifdef PVB_HOST_RESEARCH
    allocation66_.reset();
#endif
    lim_.reset();''')
 rep(p,'        // Keep this small delay warm even when diagnostics are off:', '''#ifdef PVB_HOST_RESEARCH
        if(p1pppEffective_ && allocation66_.mode())
            allocation66_.tick(eqL,eqR,layL,layR,sr_);
#endif
        // Keep this small delay warm even when diagnostics are off:''')
 p=W/'tools/pvb-harness/pvb_capi.cpp'
 with p.open('a',encoding='utf-8') as f:f.write('''
#ifdef PVB_HOST_RESEARCH
extern "C" int pvb_set_allocation66(void* p,int mode,int high,int recovery) {
 return p && static_cast<pvb::Engine*>(p)->setAllocation66(mode,high!=0,recovery)?1:0;
}
#endif
''')
args=['g++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Wpedantic','-Werror','-fPIC','-shared','-DPVB_HOST_RESEARCH=1','-I'+str(C)]
args += [str(C/f) for f in ['pvb_engine.cpp','pvb_analysis.cpp','pvb_vb.cpp','pvb_vb52.cpp']]+[str(W/'tools/pvb-harness/pvb_capi.cpp'),'-o',str(O/'build_host/libpvbcapi.so')]
(O/'build_host').mkdir(exist_ok=True);(O/'BUILD_COMMAND.json').write_text(json.dumps(args,indent=2)+'\n')
with (O/'BUILD.log').open('w') as f:subprocess.run(args,check=True,stdout=f,stderr=subprocess.STDOUT)
subprocess.run(['git','-C',str(W),'diff','--check'],check=True)
(O/'engine.diff').write_bytes(subprocess.check_output(['git','-C',str(W),'diff']))
print('built',flush=True)
