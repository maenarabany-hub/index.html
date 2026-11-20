// Bulles « cocon » (1080x1920) : node gen.js
const {chromium}=require('playwright');
const C='#4A3226', M='#B07A45';
const S=`fill="none" stroke="${C}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"`;
const icons={
 ours:`<svg viewBox="0 0 200 200"><circle cx="58" cy="62" r="24" ${S}/><circle cx="142" cy="62" r="24" ${S}/><circle cx="58" cy="62" r="10" fill="${M}"/><circle cx="142" cy="62" r="10" fill="${M}"/><circle cx="100" cy="110" r="62" ${S} fill="#F6EFE6"/><ellipse cx="100" cy="132" rx="26" ry="20" fill="${M}" opacity=".35"/><circle cx="78" cy="100" r="6" fill="${C}"/><circle cx="122" cy="100" r="6" fill="${C}"/><path d="M92 124 Q100 132 108 124" ${S} stroke-width="6"/><path d="M100 132 V142" ${S} stroke-width="6"/></svg>`,
 sapin:`<svg viewBox="0 0 200 200"><path d="M100 22 l8 16 18 2 -13 12 4 18 -17 -9 -17 9 4 -18 -13 -12 18 -2Z" fill="${M}"/><path d="M100 70 L56 128 H80 L46 172 H154 L120 128 H144 Z" ${S}/><path d="M100 172 V190" ${S}/><circle cx="86" cy="138" r="6" fill="${M}"/><circle cx="116" cy="154" r="6" fill="${M}"/><circle cx="104" cy="112" r="6" fill="${M}"/></svg>`,
 danse:`<svg viewBox="0 0 200 200"><circle cx="104" cy="34" r="16" fill="${C}"/><path d="M100 56 L94 112 M96 66 C120 54 140 36 150 14 M96 70 C76 80 58 84 38 76 M94 112 L60 186 M94 112 C120 118 150 112 176 96" ${S}/><path d="M76 122 C88 104 108 104 118 122 L92 132Z" fill="${M}" opacity=".7"/></svg>`,
 lac:`<svg viewBox="0 0 200 200"><path d="M14 132 L66 58 L96 100 L126 46 L186 132" ${S}/><path d="M112 66 L126 46 L140 66" fill="${M}" opacity=".6"/><circle cx="160" cy="44" r="14" fill="${M}"/><path d="M20 156 Q40 146 60 156 T100 156 T140 156 T180 156 M40 178 Q60 168 80 178 T120 178 T160 178" ${S} stroke-width="6"/></svg>`,
 tasse:`<svg viewBox="0 0 200 200"><path d="M40 84 H140 V140 C140 164 120 180 96 180 H84 C60 180 40 164 40 140Z" ${S}/><path d="M140 100 H154 C170 100 170 132 154 132 H140" ${S}/><path d="M64 84 V100 C64 112 116 112 116 100 V84" fill="${M}" opacity=".35"/><path d="M90 66 C78 56 82 44 92 40 C100 36 104 44 100 50 C112 40 124 50 112 62 L90 70Z" fill="${M}"/></svg>`,
 halt:`<svg viewBox="0 0 200 200"><path d="M50 100 H150" ${S}/><rect x="28" y="62" width="22" height="76" rx="8" ${S}/><rect x="150" y="62" width="22" height="76" rx="8" ${S}/><rect x="10" y="80" width="16" height="40" rx="6" fill="${M}"/><rect x="174" y="80" width="16" height="40" rx="6" fill="${M}"/></svg>`,
 tel:`<svg viewBox="0 0 200 200"><rect x="56" y="20" width="88" height="160" rx="18" ${S}/><path d="M86 36 H114" ${S} stroke-width="6"/><path d="M100 132 C86 120 72 112 72 98 C72 86 86 80 100 92 C114 80 128 86 128 98 C128 112 114 120 100 132Z" fill="${M}"/><path d="M162 40 l5 14 14 5 -14 5 -5 14 -5 -14 -14 -5 14 -5Z" fill="${M}"/></svg>`,
 miel:`<svg viewBox="0 0 200 200"><rect x="50" y="40" width="100" height="22" rx="8" fill="${M}"/><path d="M58 62 H142 C166 86 170 136 148 162 C132 182 68 182 52 162 C30 136 34 86 58 62Z" ${S}/><path d="M60 66 H140 C140 84 128 82 128 96 C128 108 114 108 114 96 C114 84 80 92 76 104 C72 116 60 108 60 96Z" fill="${M}" opacity=".55"/><path d="M80 130 Q100 142 120 130" ${S} stroke-width="5" opacity=".6"/></svg>`,
};
const bulles=[['me','me','ours'],['noel','noël','sapin'],['danse','danse','danse'],['annecy','annecy','lac'],['cocon','cocon','tasse'],['sport','sport','halt'],['daily','daily','miel'],['ugc','ugc','tel']];
const html=(icon,word)=>`<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wdth,wght@1,62.5..100,400&display=block" rel="stylesheet"><style>
*{margin:0;padding:0}body{width:1080px;height:1920px;overflow:hidden;background:#E8D9C6}
.bg{position:absolute;inset:0;background:radial-gradient(circle at 50% 50%,#FBF6EF 0 22%,#EFE3D3 45%,#DCC6AC 80%)}
.grain{position:absolute;inset:0;opacity:.18;mix-blend-mode:multiply}
.in{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center}
.in svg.i{width:400px;height:400px}
.w{font-family:'Noto Serif';font-style:italic;font-variation-settings:'wdth' 80;font-size:130px;color:#4A3226;margin-top:6px;letter-spacing:-1px}
</style></head><body><div class="bg"></div>
<svg class="grain" width="1080" height="1920"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .3  0 0 0 0 .2  0 0 0 0 .1  0 0 0 .9 0"/></filter><rect width="100%" height="100%" filter="url(#n)"/></svg>
<div class="in">${icon.replace('<svg ','<svg class="i" ')}<div class="w">${word}</div></div></body></html>`;
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
for(const [f,w,i] of bulles){await p.setContent(html(icons[i],w),{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);await p.screenshot({path:`${__dirname}/${f}.png`});}
await b.close();})();
