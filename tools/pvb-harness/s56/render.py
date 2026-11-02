"""Render only P1/P1+++/fixed modified c. Original input stays in place; output must be in listen/."""
import argparse, json, sys
from pathlib import Path
import soundfile as sf
from compare import Engine, library
p=argparse.ArgumentParser();p.add_argument("input",type=Path);p.add_argument("output",type=Path);p.add_argument("--mode",choices=["p1","p1ppp","reference-c"],required=True);p.add_argument("--lib",type=Path,required=True);a=p.parse_args()
allowed=Path("/mnt/c/Users/ksysh/rootnote-duo/listen").resolve()
if not a.output.resolve().is_relative_to(allowed):p.error("output must be under the approved listen/ folder")
x,sr=sf.read(a.input,dtype="float32",always_2d=True)
if x.shape[1]==1:x=x.repeat(2,axis=1)
if x.shape[1]!=2:p.error("stereo or mono input required")
if a.mode=="p1ppp" and sr!=48000:p.error("P1+++ supports 48 kHz only")
if a.mode=="reference-c":
 l=library(a.lib);h=l.pvb_vb_create(16,sr)
 if not h:p.error("ID16 reference requires an explicit --reference library")
 l.pvb_vb_destroy(h)
e=Engine(a.lib,sr,on=a.mode=="p1ppp",algo=16 if a.mode=="reference-c" else 6)
y,_,_=e.run(x,256);e.close();a.output.parent.mkdir(parents=True,exist_ok=True)
sf.write(a.output,y,sr,subtype="FLOAT");a.output.with_suffix(a.output.suffix+".json").write_text(json.dumps(dict(mode=a.mode,sample_rate=sr,library=str(a.lib.resolve()),source="archive 9d408fb -> s56 option B"),indent=2))
