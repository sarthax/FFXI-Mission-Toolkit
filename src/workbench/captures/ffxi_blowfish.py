"""Dependency-free FFXI/LandSandBoat Blowfish-variant primitive.

The seed constants are the standard Blowfish hexadecimal digits of pi, encoded here as data. The
FFXI packet path uses a nonstandard round function, so generic Blowfish implementations are not
wire-compatible. Blocks use little-endian uint32 words to match the server packet path.
"""
from __future__ import annotations

import base64
import struct

_MASK32 = 0xFFFFFFFF
_PI_BYTES = base64.b85decode(
    'BtL41g`)`56B&vw18{RhqzO18DW5UW2rl}V>`rWnMJOTWIM5S!zEoz<H0ca%z^o~^$$U`VKZMn_wMPjTk`~q3iFx}Q(J>3AnBTRm'
    'Fa2`c&>G*jxZ$tuY9@Y`x_ppD@hpFtB%zr{vyp7~2m$iqg^v6dV`(7RaaT@hq*(r=^pib)4V83{a*noGaf{7Zf)z^cdsL(y!dh9i'
    'oG{fnD)L|x#nG@MC}4%~%0YP;xZ61Ij(Oa$U^*BMY@QB_upWv&*A;icy)jECc&{(oRbX6T=2a#0s#U9$S4fy*W9Sq>RmwSPDytB-'
    'w9H&I5kctAp;U&id~)fNv+fiTV{g1FE2+g@bQm%A&Rjkgn}?GguhzOVY$VTIdNNaiD3ykHJC8`1YfHJW#J}hpW+)+(Vb}@G`yr{3'
    'NPMhdUF?7|?}S}l>4kN%+$JLe>t!2=BZ)qN)0V8o4{dMrgY-f<E(=70q=X;@X~^(Oo*$cDA;xGz_UUYzXAGQStJ8?^YEhul*i<iQ'
    'mJg>Wt5GwfZtn|h6M8%3x;yYte)}qzq48xMIj;eBX3AMUf<q37jP8aRMQ@+9eT1dMJBwbv;BR%<g~1?mKpI4!R>5kfPSdJlHa~X;'
    '8~)#NLYo3TH_+E4&<YYr+Yjo~N%6p&2UBv%fSDV6CDeJ?_UPXC<Ni<@ws}lDmu%p@1i%Km!KqKSK%Zd5UR<8S8EPbBX!~!kK5SF9'
    '6FIW$J5ua#ZTwLmn=q9u%z;HjuU@?gzT?mY-ZM)5W)CO_87@n+z{{vtMaXmy(hFZXxzqdGRe8X@8elRC)}a8#KrC{3XP+hh`yZps'
    'j-~1N+cF~fJarb|{b6erFHj!Htp!r6GCj5W{Ue89Q!#r;J^<f>o?KVE%5RLI8i!Uc-xq1y)k3KDD1QILtY<RDj89c_X<H|-yUJL|'
    ';s2vuxbP965c)ls{UL+6O8m8KEz#3knp5O?w)jP5(vC^IOZ%6Q;ob7uq|1IYV*3+8&g91E?;y(BHg`+`(0-o&EAbz+mD}1)u8@(K'
    '>aC7(Ym?QW(2mj2ug4|ejyzj0j&+o`kM`pG@)9d#h={lnkPYx0Ppw{{Xph4j(a-Ubv#7zXFE1h(z77|6>UAytivk~^<)F+DwQqFj'
    '7_9Tw&WYlgw5U(u{S)A~e8f9}(ygf37GI)ffR%Rzlgx7zAsQ5S=B*%QceVP4$5cY~`<*q<>&>qWdp?Pv)<GN7t{#3#03{ABAaS!^'
    'B4_}+SGeG>BxE+5@CmsdRb!DIS>L9rc)>%7*;-S7Abne+0_C~IgC+xZVwKOS5y%;6PIF2@vqvq;dlack8&LpKno}ti)(=-dyqm`4'
    'D`2E{f#!4o2)b{zR~zXc@|NstDh=5cwqs=>=ehZ||1<?I#f4U6Q?M;vsh^Lb2)aj^ZiNSGOL}nWwX-Qi+jR*p#2F?dt!}2UNvGd^'
    'obF(_kL|K%?5d1$X_^=RR%B9a!m*y=88!l?bqP!<pji_@<QO_WKUA2STSA>>YmemCnfE`|q0*cO@8~e~O)WU)@FiWrOx+-cgmCL7'
    'V}j|%0v^m>3219SKDzJ8JeL?0Yie+zXn!??QlR37x13W2s!#_vJ_m#xf8MTKj(tSzR~GWPusYf|@K6j5@Ejim0syoBt_<}WJhgPP'
    'C4+ic+zBDQ(UBARe5o(?lrl$iBK1cBI_2eoH^SQ7$hCGfn)BVKsYGE$56}Y+?8wJHq;(!a;yBHjJL(QEGJw0G7(TNxPE?CHPi?sf'
    'Z$b?N_6h{QEVvSoB$s@7R(Y^;yswF`-kNtG*^>wmvx}}0+|NHQRT6R^E^BclP#WFlpM=eadRRvobO_oPyq}u9=}Uc#?0W1v+l3wa'
    'V+liM#AL(L?;IFMG8Nef-9tM!B*MBD5}{2)DrLk`P?P`y6FTJGao_l!5HU_wfvk7dUlAFb1T|Li*Q3X4JP{Z>StO+i@{i{2m+|}h'
    'p1Qv*9u+)phT}zW>gjK>h7Mi|T0SbXcOT~*PCW+tDP`Qbndco3fIf-VQf9~{E=<XIoDj2W#uW~_l;Y}mrTjco9tth=^7l@sHXSQH'
    '8962o8NzvBQX{7b_Y)Gf>#hE7>cbyq<Ge+crhCYPv41zw0gV4B!!q6PzHC~hWmqAFXseh4?#`tT+b@+nD(`)*TW&9e6(P1LDF<P2'
    '?A=FoVV@Nc6U?YE>tVf?12p~~ssm%swR2pMOmLz()t;UU%c|ZK?#za~U}7w%oU2@`vh##)WQ!iJ8NKkzpd)FyWm>yXKxkSrJSw!a'
    'F`ntwz#+Kzn^X%KhhLzXmG_x`Vm*DR_&11}m*XvW5$%&-7HATI4mF4=$L1f_mfqi?cv!lbSM`LY8zORJn}fsu8p1}F&9e&YQ!X%6'
    'kJ(7%ZM-okSnKldG{*nx{wVEX?tDCRT}l+$=w!F!LJ(aPAU+e|MegFZqpGXw+iXu2`pZwy$3pZ%?`pfXWluXDLCqlr*dBSFhJ{VX'
    '<V#0tJ%M6S&tjqSTa6}0{D^~~!N<0ve-$LdY0GqyM}&$CR+6%X30uDatr<w26k@S-BZ3Y9SVD~|3{~~&9j){}BR_CqGji~fjgx*s'
    ')?e)LY$7|`eBL)%%kFewK!x(B&UZ3yrU!t88Te41=<nE7VcC~8scEOG#S8|*S_G^7fD6jpo<w>s!$mZN{ncj$4j!J#+jHB~5LJlH'
    'XJ6WR<7Y!a#l$paaXvWMJt+8|@ooPg6+R*7kFY&T=Hs6$+k>t5={;I#lz~9^_Dm)mlxZn6K@}kPb^_G*y!2}>)S>`r)CeSTGa&S8'
    'L$}noPyk`C9y#_dmn20-6d_M^zl(@KO_lr|mbH<uaP-~NW}q)czq|?T1HG4pf2?iLG0TMnmg^_8RsA_Z+9gNktI7(RC{TDMQv@mW'
    '3M_`&>9%eAXxtQH*GOpqXb!-nC!vk*Pe1;m=!dP0wT$2fdi2(|s?HvK(>Gu2&UmAlKx-;OApV{;+4F_D?m5@1I}%Qd9m)FlOKlid'
    'CZlFC>f@KPI&S)O-CIL4XhG-q%6K6A`wI0=*#5JZML<@px=58LRZ}`TAcKvE{%fhX(3X`;Rj6mYp%t1~%&943nc>?rrYcHSKQSfw'
    'Ui5w(kSQ^I{rKnt1Sc<WfV&l31t=`zmBAHA<i>3xNWl|7#}9_w2l>hFK?ENUKu39`U5IWMGG9^a)tkW4^1Q*1K@l}%C3|=@U@Dwo'
    '-}vaGA7gAA4idD&0^u^AuVzot%F%%pYa^B5Gd_~xJ0uHY?!LJqg|ea!=DH1;-f|3#Eu!}*&=Pn>mA91rWPJ!?=gjr+R7s<6hkZ!;'
    '!=3#n^FECp3P)o>nJ)iyI&W^P^!WWZs1n>@q3hlFnH%9u+iq(O#(Px|ZD%YuCuP(-+|cL*@hJ_*%mDwRwK)%xX%FoSW_zFe&f9&Q'
    'ppnlD*%e-+yAv;nQCqDfdz5*<c01PVH#sh|%n@06fF|OX^e!<iXhN;0#%e1&5_L?>crNiAY7#;>w~|rk2BEv=OZ#I`8fy?35z6iQ'
    'Jte)^;^D)|L_!u>3KA2B*$nJ%)vM|%WUpsV+J>lKzQ5^+WaPvCoxFfo@b|!mV0e4@U;|)H(fxx)_BbD~cSWuQ*EamjgF<UF@E)si'
    'uz*2_JOEx_cc53kz38qaRYpRYzgR9|PFVDh^4<NS^mOkyhl#zyQ)c<Y$g_@gv~}`TM*P{idg~@(iyhyDglZ0XkzbYKMs8V-AhcI-'
    'jMY_<$pYR?xeKh}yMhJK5vXEFb#$qow|^P7;HlgRW-SS!#4<)R=vp5F3Glv*N|~S~9d7;*8o50k3#Fvrp@#AgC}{C%+_&0;S2+g$'
    'q2kV)PtAW)P!V1Mrv`)ipaQkT4d&1%n)r+-cRz+f!(dDXVW<YR@E3Y0!1adU0AN_EFx-7&5$2xPBRJ|~Q^MVp!on6byUXrYki53u'
    '>->G8&RHFHZw2HDOMC%{IdTd;e3E=5hU0Qya!sAN8o^t%)1J8e?Nn8G2>hkB*gbsHO|1{a9#HRIv0>);qJ<RMY*7<DZ`H@=R^d*>'
    'HY&f)-Nwi_*P1dkl4F7rXAb&~KwtpiIyufa)B5$#tHO6TTE#6JT(D=JPop<N(}E{JnY^36)e(-JzYlX2)-4=<#{k58w~QNWA)$~('
    'vTm`yYBp}PS4gWbyp(Qv#-n!9Wl6%wQxEv=MvdNm)pH6ROwdinDLK2_sk%l`td%C{zFy-5q59SEYAsQkWABXOnuhKoz=^`RLnJQt'
    'r5*#Sobu45gTP_Bo9SvzkL49mx@23{C?=x$r#d>}OR1HH?^R;y$1m^G_fq%TKLl@SclruhfaIwahp>hLn+fKvJ3i%;>5%<eo;25&'
    'EbzD40xOGAmes5}0ez-@(a%2Ce0?n_AD<=9t@5~=TGq63T8Q;b;3=$e;2EXnN3g8@?UVYO=+nfFC_7io_|;}9c@r)ucwYgL?R8*P'
    '_m&Ps<I`S@6$Ne7i1cl`1EFCh1!VBO!|R?EJdjtSmnRzRsX7NL8$WHE9%CW(^_*t=CfxHGbu-y0u~q%`16DMGin=_zC{cG2!V1~='
    'tISbn%&n4NP3RX<I56CfH=S5wlOXw#>UxmE`#yWlQ6bJ`cTc`DsJ7#N!zn#RNZwOvWE19qqOJ%K-EFcYX@xEQ2?rr&vzkT<WJSQ;'
    'SZv<U93aT9TfX<*8(57%%+djWYqaCL-J)uKI$8fkJ~awNytK{La_Y{g`ecN=jb;+AzdUb8(wpRCR4-kguEKX4_D*APbPf%T=UWq3'
    '_;MC;uTy<pKtRg~PPF38G}1<D0Tr)=;jjcKm6$pm2DqQJ&TgPcZ$CSNH6W{k0U8}kCvqqFVHIGp=aWC&yE=I*G({!7polr)QO<cw'
    'FEYuupdY%);2g+)yvNb@&jAs`q3Ei|8jy!c)K9&d(AwV1)e71;13AMg#*sE>jrlQr;IS)D_nuj|L-o5l^3@stC)q`uzn3B`73TaZ'
    '50U(Fo0JtL`sI^h&bFNE!l-0f61u3-w!sHp;{|FA5YkX(%LAlB;OuS=7MR;ROqig)GI;4^pC6Sn;M0=d)1WjfiE;8C8wzwmOQST5'
    '#lCSM!*(**-!-3&o0%^z<_m8}599G2<xJXC9@^NE&SH7b%|3o_78tQ+{VW{?gpbn2_WL54^&|6FrZRRTlc+T@R?N);tnh(iT6OES'
    'ZWcC|h|+V+-j-sLfw@W0Oi+*;amH2@=EldpGI|sWMd8o}!}5EY$*NQRVyF)QyCuKkHNDdIaS~|-vIGJmw#(0a&32qCQxQJE7C__E'
    'IIF#2B}c9Bx;P-5_eRckcdwzvAa!71h0Fd<is+5ldaC)bO!=yQ8A!rh0{e=L0mEwK*6ZQ<kkt5Trd-~jKM5r*!U*P{w@zU)&UfNl'
    'SC8N0I>U12'
)
_WORDS = struct.unpack(">1042I", _PI_BYTES)
_INITIAL_P = _WORDS[:18]
_INITIAL_S = _WORDS[18:]

def _tt(working: int, s) -> int:
    return ((((s[256 + ((working >> 8) & 0xFF)] & 1) ^ 32)
             + ((s[768 + ((working >> 24) & 0xFF)] & 1) ^ 32)
             + s[512 + ((working >> 16) & 0xFF)]
             + s[working & 0xFF]) & _MASK32)

def encipher_words(xl: int, xr: int, p, s) -> tuple[int, int]:
    xl &= _MASK32; xr &= _MASK32
    for i in range(16):
        xl = (xl ^ p[i]) & _MASK32
        xr = (_tt(xl, s) ^ xr) & _MASK32
        xl, xr = xr, xl
    xl, xr = xr, xl
    return (xl ^ p[17]) & _MASK32, (xr ^ p[16]) & _MASK32

def decipher_words(xl: int, xr: int, p, s) -> tuple[int, int]:
    xl &= _MASK32; xr &= _MASK32
    for i in range(17, 1, -1):
        xl = (xl ^ p[i]) & _MASK32
        xr = (_tt(xl, s) ^ xr) & _MASK32
        xl, xr = xr, xl
    xl, xr = xr, xl
    return (xl ^ p[0]) & _MASK32, (xr ^ p[1]) & _MASK32

def init_key(key: bytes) -> tuple[list[int], list[int]]:
    if not key:
        raise ValueError("key must not be empty")
    p = list(_INITIAL_P); s = list(_INITIAL_S)
    key_index = 0
    for i in range(18):
        data = 0
        for _ in range(4):
            data = ((data << 8) | key[key_index]) & _MASK32
            key_index = (key_index + 1) % len(key)
        p[i] = (p[i] ^ data) & _MASK32
    left = right = 0
    for i in range(0, 18, 2):
        left, right = encipher_words(left, right, p, s)
        p[i], p[i + 1] = left, right
    for box in range(4):
        base = box * 256
        for j in range(0, 256, 2):
            left, right = encipher_words(left, right, p, s)
            s[base + j], s[base + j + 1] = left, right
    return p, s

def transform_blocks(data: bytes, key: bytes, *, decrypt: bool) -> bytes:
    if len(data) % 8:
        raise ValueError("FFXI Blowfish block data must be 8-byte aligned")
    p, s = init_key(key)
    out = bytearray(data)
    transform = decipher_words if decrypt else encipher_words
    for offset in range(0, len(out), 8):
        left, right = struct.unpack_from("<II", out, offset)
        left, right = transform(left, right, p, s)
        struct.pack_into("<II", out, offset, left, right)
    return bytes(out)

def encrypt_blocks(data: bytes, key: bytes) -> bytes:
    return transform_blocks(data, key, decrypt=False)

def decrypt_blocks(data: bytes, key: bytes) -> bytes:
    return transform_blocks(data, key, decrypt=True)
