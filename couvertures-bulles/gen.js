// Génère les couvertures des bulles à la une (1080x1920) : node gen.js
const {chromium}=require('playwright');const fs=require('fs');
const R='#E8B0B0',C='#8E2A30';
const S=`fill="none" stroke="${R}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"`;
const cherry=`<svg viewBox="0 0 200 200"><path d="M100 30 C90 70 70 95 62 120 M100 30 C110 70 128 100 138 125" ${S}/><path d="M100 30 C120 18 150 22 162 40 C140 48 118 44 100 30Z" fill="${R}"/><circle cx="60" cy="148" r="34" fill="${R}"/><circle cx="140" cy="150" r="34" fill="${R}"/><path d="M46 136 a16 16 0 0 1 14 -10 M126 138 a16 16 0 0 1 14 -10" stroke="#561519" stroke-width="6" fill="none" stroke-linecap="round"/></svg>`;
const mirror=`<svg viewBox="0 0 200 200"><ellipse cx="100" cy="82" rx="52" ry="64" ${S}/><path d="M100 146 V188 M74 188 H126" ${S}/><path d="M78 64 l16 -16 M82 86 l30 -30" stroke="${R}" stroke-width="6" stroke-linecap="round" opacity=".7"/></svg>`;
const collab=`<svg viewBox="0 0 200 200"><path d="M100 40 l10 30 30 10 -30 10 -10 30 -10 -30 -30 -10 30 -10Z" fill="${R}"/><path d="M152 118 l6 17 17 6 -17 6 -6 17 -6 -17 -17 -6 17 -6Z" fill="${R}"/><path d="M48 128 l5 14 14 5 -14 5 -5 14 -5 -14 -14 -5 14 -5Z" fill="${R}"/><path d="M40 60 l3 8 8 3 -8 3 -3 8 -3 -8 -8 -3 8 -3Z" fill="${R}" opacity=".6"/></svg>`;
const martini=`<svg viewBox="0 0 200 200"><path d="M40 50 H160 L100 118Z" ${S}/><path d="M100 118 V180 M70 182 H130" ${S}/><circle cx="132" cy="44" r="15" fill="${R}"/><path d="M132 30 C136 18 146 12 154 10" ${S} stroke-width="5"/></svg>`;
const fork=`<svg viewBox="0 0 200 200"><circle cx="100" cy="110" r="66" ${S}/><circle cx="100" cy="110" r="44" ${S} stroke-width="4" opacity=".6"/><path d="M22 40 V186 M12 40 V72 a10 10 0 0 0 20 0 V40" ${S} stroke-width="6"/><path d="M186 186 V40 C168 50 166 90 174 110 H186" ${S} stroke-width="6"/></svg>`;
// [fichier, mot (Noto Serif), taille, étiquette (CY Grotesk), icône]
const covers=[
 ['me','Me',300,'Maena',mirror],
 ['collabs','Collabs',175,'Marques & co',collab],
 ['her','Her',300,'Soirées',martini],
 ['becoming','Becoming',145,'Chaque lundi',cherry],
 ['annecy','Annecy',180,'À croquer',fork],
];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
const t=fs.readFileSync(__dirname+'/template.html','utf8');
for(const [f,w,s,tag,ic] of covers){await p.setContent(t.replace('__ICON__',ic).replace('__WORD__',w).replace('__SIZE__',s).replace('__TAG__',tag),{waitUntil:'networkidle'});
await p.evaluate(()=>document.fonts.ready);await p.screenshot({path:`${__dirname}/${f}.png`});}
await b.close();})();
