[L] BUILD  M=2  S=6
desc: 出片合成：素材 → 基线/比例尺/路径 → 逐帧合成 → mp4
M: BUILD/util, BUILD/phase  +TOP:build_video
uses_out: ATOM/aero,ATOM/frame,ATOM/img,ATOM/math,ATOM/path,SHOT/gen,SHOT/skel
rule: T102 T29 T31 T76 T77 T79 T80 T81 T84 T86 T91 T96 T97 T98 T99
