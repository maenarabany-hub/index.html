// Génère les couvertures des bulles à la une (1080x1920) : node gen.js
const {chromium}=require('playwright');const fs=require('fs');
const R='#E8B0B0',C='#8E2A30';
const S=`fill="none" stroke="${R}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"`;
const cherry=`<svg viewBox="0 0 200 200"><path d="M100 30 C90 70 70 95 62 120 M100 30 C110 70 128 100 138 125" ${S}/><path d="M100 30 C120 18 150 22 162 40 C140 48 118 44 100 30Z" fill="${R}"/><circle cx="60" cy="148" r="34" fill="${R}"/><circle cx="140" cy="150" r="34" fill="${R}"/><path d="M46 136 a16 16 0 0 1 14 -10 M126 138 a16 16 0 0 1 14 -10" stroke="#561519" stroke-width="6" fill="none" stroke-linecap="round"/></svg>`;
const mirror=`<svg viewBox="0 0 200 200"><ellipse cx="100" cy="82" rx="52" ry="64" ${S}/><path d="M100 146 V188 M74 188 H126" ${S}/><path d="M78 64 l16 -16 M82 86 l30 -30" stroke="${R}" stroke-width="6" stroke-linecap="round" opacity=".7"/></svg>`;
const collab=`<svg viewBox="0 0 200 200"><path d="M100 40 l10 30 30 10 -30 10 -10 30 -10 -30 -30 -10 30 -10Z" fill="${R}"/><path d="M152 118 l6 17 17 6 -17 6 -6 17 -6 -17 -17 -6 17 -6Z" fill="${R}"/><path d="M48 128 l5 14 14 5 -14 5 -5 14 -5 -14 -14 -5 14 -5Z" fill="${R}"/><path d="M40 60 l3 8 8 3 -8 3 -3 8 -3 -8 -8 -3 8 -3Z" fill="${R}" opacity=".6"/></svg>`;
const martini=`<svg viewBox="0 0 200 200"><path d="M40 50 H160 L100 118Z" ${S}/><path d="M100 118 V180 M70 182 H130" ${S}/><circle cx="132" cy="44" r="15" fill="${R}"/><path d="M132 30 C136 18 146 12 154 10" ${S} stroke-width="5"/></svg>`;
const fork=`<svg viewBox="0 0 200 200"><circle cx="100" cy="110" r="66" ${S}/><circle cx="100" cy="110" r="44" ${S} stroke-width="4" opacity=".6"/><path d="M22 40 V186 M12 40 V72 a10 10 0 0 0 20 0 V40" ${S} stroke-width="6"/><path d="M186 186 V40 C168 50 166 90 174 110 H186" ${S} stroke-width="6"/></svg>`;
const dumbbell=`<svg viewBox="0 0 200 200"><path d="M50 100 H150" ${S}/><rect x="28" y="62" width="22" height="76" rx="6" fill="${R}"/><rect x="150" y="62" width="22" height="76" rx="6" fill="${R}"/><rect x="10" y="78" width="16" height="44" rx="5" fill="${R}"/><rect x="174" y="78" width="16" height="44" rx="5" fill="${R}"/></svg>`;
const hanger=`<svg viewBox="0 0 200 200"><path d="M86 52 a14 14 0 1 1 22 12 c-6 4 -8 8 -8 16 L176 140 c6 4 4 12 -4 12 H28 c-8 0 -10 -8 -4 -12 L100 80" ${S}/></svg>`;
const matcha=`<svg viewBox="0 0 200 200"><path d="M24 96 H176 C176 146 144 176 100 176 C56 176 24 146 24 96Z" ${S}/><path d="M36 96 C70 84 130 84 164 96Z" fill="${R}" opacity=".85"/><path d="M78 76 C68 62 88 50 78 34 M104 74 C94 58 116 46 104 26 M130 76 C120 62 140 50 130 34" ${S} stroke-width="5" opacity=".8"/><path d="M148 140 C160 128 178 128 186 120 C184 136 168 150 148 140Z" fill="${R}"/></svg>`;
const ballet=`<svg viewBox="0 0 200 200"><circle cx="104" cy="34" r="16" fill="${R}"/><path d="M100 56 L94 112 M96 66 C120 54 140 36 150 14 M96 70 C76 80 58 84 38 76 M94 112 L60 186 M94 112 C120 118 150 112 176 96" ${S}/><path d="M80 118 C88 104 104 104 112 118" ${S} stroke-width="5"/></svg>`;
const column=`<svg viewBox="0 0 200 200"><circle cx="150" cy="44" r="22" fill="${R}"/><path d="M40 70 H130 M46 82 H124 M56 82 V164 M76 82 V164 M94 82 V164 M114 82 V164 M44 164 H126 M36 180 H134" ${S}/><path d="M36 70 C40 60 50 60 54 66 M134 70 C130 60 120 60 116 66" ${S} stroke-width="5"/></svg>`;
const lunettes=`<svg viewBox="0 0 200 200"><path d="M16 92 H184" ${S}/><path d="M24 92 H90 C90 128 76 146 56 146 C34 146 24 126 24 92Z" fill="${R}"/><path d="M110 92 H176 C176 126 166 146 144 146 C124 146 110 128 110 92Z" fill="${R}"/><path d="M90 98 C96 90 104 90 110 98" ${S} stroke-width="5"/><path d="M150 30 l5 14 14 5 -14 5 -5 14 -5 -14 -14 -5 14 -5Z" fill="${R}"/></svg>`;
const camera=`<svg viewBox="0 0 200 200"><rect x="22" y="60" width="156" height="112" rx="22" ${S}/><path d="M70 60 L82 38 H118 L130 60" ${S}/><circle cx="100" cy="116" r="32" ${S}/><circle cx="100" cy="116" r="14" fill="${R}"/><circle cx="152" cy="84" r="7" fill="${R}"/></svg>`;
// [fichier, mot (Noto Serif), taille, étiquette (CY Grotesk), icône]
const covers=[
 ['me','Me',380,'Maena',mirror],
 ['collabs','Collabs',380,'Brands',collab],
 ['her','Her',380,'Lifestyle',lunettes],
 ['becoming','Becoming',380,'Lundi',cherry],
 ['annecy','Annecy',380,'À croquer',fork],
 ['sport','Sport',380,'Move',dumbbell],
 ['style','Style',380,'Outfits',hanger],
 ['matcha','Matcha',380,'Ma pause',matcha],
 ['danse','Danse',380,'Dance',ballet],
 ['daily','Daily',380,'Vraie vie',camera],
 ['greece','Greece',380,'Voyage',column],
];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
const t0=fs.readFileSync(__dirname+'/template.html','utf8');const t=t0;
for(const [f,w,s,tag,ic] of covers){await p.setContent(t.replace('__ICON__',ic).replace('__WORD__',w).replace('__SIZE__',s).replace('__TAG__',tag),{waitUntil:'networkidle'});
await p.evaluate(()=>document.fonts.ready);await p.evaluate(()=>{const w=document.querySelector('.w');let f=parseFloat(w.style.fontSize);const g=document.querySelector('.tag');let tf=72;while(g.offsetWidth>600&&tf>40){tf-=2;g.style.fontSize=tf+'px';}while(w.scrollWidth>700&&f>80){f-=4;w.style.fontSize=f+'px';}g.style.marginBottom=(-0.09*f)+'px';});await p.screenshot({path:`${__dirname}/${f}.png`});}
await b.close();})();
