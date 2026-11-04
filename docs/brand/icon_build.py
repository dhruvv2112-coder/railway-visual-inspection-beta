import numpy as np, sys
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
B='docs/brand/'
src=np.asarray(Image.open(B+'ontrack-ai-icon.png').convert('RGBA')).astype(float)
S=src.shape[0]; r,g,b,a=[src[...,i] for i in range(4)]; ins=a/255
red=np.clip((r-np.maximum(g,b)-20)/150,0,1)*ins
dark=np.clip((235-np.maximum(np.maximum(r,g),b))/215,0,1)*ins*(1-red)
lab,n=ndimage.label(dark>0.15)
kill=np.zeros_like(dark,bool)
for i,sl in enumerate(ndimage.find_objects(lab),1):
    x0,x1,y0,y1=sl[1].start,sl[1].stop,sl[0].start,sl[0].stop
    corner=(x1<0.4*S or x0>0.6*S) and (y1<0.4*S or y0>0.6*S)
    if corner: kill|=ndimage.binary_dilation(lab==i,iterations=3)
yy,xx=np.mgrid[0:S,0:S]
kill|=((yy<0.1*S)&(xx>0.65*S))|((xx>0.91*S)&(yy<0.34*S))
thick=2*ndimage.distance_transform_edt(lab==[i for i,sl in enumerate(ndimage.find_objects(lab),1) if sl[1].stop<0.4*S and sl[0].start>0.6*S][0]).max()
dark=dark*(~kill)
# wire end: centerline per column
cols=[x for x in range(S) if red[:,x].max()>0.5]
xe=max(cols); pts=[(x,(np.arange(S)*red[:,x]).sum()/red[:,x].sum()) for x in range(xe-80,xe+1) if red[:,x].sum()>0]
px=np.array(pts); k=np.polyfit(px[:,0],px[:,1],1)
wthick=red[:,xe-40].sum()
def lay(al,col):
    o=np.zeros((S,S,4)); o[...,:3]=col; o[...,3]=np.clip(al,0,1)*255; return Image.fromarray(o.astype('uint8'),'RGBA')
strokes=lay(dark,(255,255,255)); wire=lay(red,(255,216,77))
def render(C,fx,fy,fs,bg=None,glass_edge=False,SS=4):
    """canvas C px; tile frame at (fx,fy) size fs"""
    Cs=C*SS; out=Image.new('RGBA',(Cs,Cs),(0,0,0,0))
    if bg is not None: out.alpha_composite(bg.resize((Cs,Cs),Image.LANCZOS))
    F=fs*SS; X0,Y0=fx*SS,fy*SS
    R=0.225*F; dc=0.15*F; w=thick/S*0.70*F; arm=0.37*F; sc=0.68
    a=int(F*sc); ox=int(X0+(F-a)/2); oy=int(Y0+(F-a)/2); f=a/S
    # wire extension to bracket centerline
    ext=Image.new('RGBA',(Cs,Cs),(0,0,0,0)); de=ImageDraw.Draw(ext)
    xb=X0+F-dc; x_src=(xb-ox)/f; y_src=np.polyval(k,x_src)
    p0=(ox+xe*f, oy+np.polyval(k,xe)*f); p1=(xb, oy+y_src*f)
    ww=max(2,wthick*f)
    de.line([p0,p1],fill=(255,216,77,255),width=int(ww)); de.ellipse((p0[0]-ww/2,p0[1]-ww/2,p0[0]+ww/2,p0[1]+ww/2),fill=(255,216,77,255))
    wl=wire.resize((a,a),Image.LANCZOS); wl2=Image.new('RGBA',(Cs,Cs),(0,0,0,0)); wl2.alpha_composite(wl,(ox,oy)); wl2.alpha_composite(ext)
    glow=Image.new('RGBA',(Cs,Cs),(255,196,60,0)); glow.putalpha(wl2.getchannel('A')); glow=glow.filter(ImageFilter.GaussianBlur(F/90))
    st=Image.new('RGBA',(Cs,Cs),(0,0,0,0)); st.alpha_composite(strokes.resize((a,a),Image.LANCZOS),(ox,oy))
    d=ImageDraw.Draw(st); W=(255,255,255,255); iw=int(round(w))
    for cx,cy,s0 in [(X0+R,Y0+R,180),(X0+F-R,Y0+R,270),(X0+F-R,Y0+F-R,0),(X0+R,Y0+F-R,90)]:
        rr=R-dc
        d.arc((cx-rr-w/2,cy-rr-w/2,cx+rr+w/2,cy+rr+w/2),s0,s0+90,fill=W,width=iw)
    E=[]  # arms: along each edge from arc end to arm length
    L=[(X0+dc,Y0+R,X0+dc,Y0+arm),(X0+R,Y0+dc,X0+arm,Y0+dc),
       (X0+F-R,Y0+dc,X0+F-arm,Y0+dc),(X0+F-dc,Y0+R,X0+F-dc,Y0+arm),
       (X0+F-dc,Y0+F-R,X0+F-dc,Y0+F-arm),(X0+F-R,Y0+F-dc,X0+F-arm,Y0+F-dc),
       (X0+R,Y0+F-dc,X0+arm,Y0+F-dc),(X0+dc,Y0+F-R,X0+dc,Y0+F-arm)]
    for x1,y1,x2,y2 in L:
        d.line([(x1,y1),(x2,y2)],fill=W,width=iw); d.ellipse((x2-w/2,y2-w/2,x2+w/2,y2+w/2),fill=W)
    shadow=Image.new('RGBA',(Cs,Cs),(8,10,40,0)); shadow.putalpha(st.getchannel('A').point(lambda v:int(v*0.35))); shadow=shadow.filter(ImageFilter.GaussianBlur(F/120))
    out.alpha_composite(shadow,(0,int(F/160))); out.alpha_composite(st); out.alpha_composite(glow); out.alpha_composite(glow); out.alpha_composite(wl2)
    return out.resize((C,C),Image.LANCZOS)
