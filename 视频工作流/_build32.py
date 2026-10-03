import cv2, numpy as np, sys, os
sys.path.insert(0,'.')
import _layer_style as L

BATCH=['批1_帧00-07','批2_帧08-15','批3_帧16-23','批4_帧24-31']
FPS=32; DUR=8.0; SPEED=1.5; OUT_W=576

def key_color_of(im):
    h,w=im.shape[:2]
    return np.median(np.array([im[5,5],im[5,w-5],im[h-5,5],im[h-5,w-5]],np.float32),axis=0)

def key_alpha(cell,key):
    d=np.abs(cell.astype(np.int16)-key).sum(2)
    m=(d<75).astype(np.uint8)*255
    m=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
    return cv2.GaussianBlur(255-m,(0,0),1.5)

bg0=cv2.imread('_生成/城墙背景.png')
oh,ow=bg0.shape[:2]; sc=OUT_W/ow
bg0=cv2.resize(bg0,(OUT_W,int(oh*sc)),interpolation=cv2.INTER_AREA)
H,W=bg0.shape[:2]
PX_PER_M=120.0*sc; BASE_Y=int(878*sc)
print(f'画布{W}x{H} sc={sc:.3f} px/m={PX_PER_M:.1f} 基线={BASE_Y}')

cells=[]
for b in BATCH:
    im=cv2.imread(f'_生成/链式/玄奘_走_{b}.png')
    k=key_color_of(im); h,w=im.shape[:2]; gh,gw=h//4,w//2
    for r in range(4):
        for c in range(2):
            cells.append((im[r*gh:(r+1)*gh, c*gw:(c+1)*gw], k))
print('切分', len(cells), '格  背板色', np.median(np.array([k for _,k in cells]),axis=0).round(0).tolist())

def prep(item, th):
    cell,key=item
    a=key_alpha(cell,key)
    ys,xs=np.where(a>60)
    if len(ys)==0: return None
    fg=cell[ys.min():ys.max()+1, xs.min():xs.max()+1]
    al=a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    nw=max(int(fg.shape[1]*th/max(fg.shape[0],1)),1)
    return cv2.resize(fg,(nw,th),interpolation=cv2.INTER_AREA), cv2.resize(al,(nw,th),interpolation=cv2.INTER_AREA)

th=int(1.70*PX_PER_M)
prepared=[p for p in (prep(c,th) for c in cells) if p]
print('人物高', th,'px  可用帧', len(prepared))

tint=L.bg_tint_of(bg0); bmean=bg0.reshape(-1,3).mean(0)
shc={}
def sh_of(al,i):
    if i not in shc: shc[i]=L.contact_shadow(al)
    return shc[i]

n=int(FPS*DUR); step=SPEED*PX_PER_M/FPS
os.makedirs('_out32',exist_ok=True)
for i in range(n):
    bg=bg0.copy()
    for k,(dx,dy0) in enumerate([(-70,0),(0,14),(70,-11)]):
        fi=(i+k*len(prepared)//3)%len(prepared)
        fg,al=prepared[fi]; fh,fw=fg.shape[:2]
        x=int((dx+70+i*step)%(W+fw)-fw); x=max(min(x,W-fw),0)
        y=max(min(BASE_Y+dy0-fh,H-fh),0)
        roi=bg[y:y+fh, x:x+fw]
        fg2=L.global_grade(L.env_reflection(fg,al,tint), bmean)
        roi[:]=L.multiply_shade(roi, sh_of(al,fi))
        roi[:]=L.over(roi, fg2, al)
    cv2.imwrite(f'_out32/f{i:04d}.png', bg, [cv2.IMWRITE_PNG_COMPRESSION,1])
print('输出帧', n)
