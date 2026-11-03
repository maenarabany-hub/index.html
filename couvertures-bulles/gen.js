const {chromium}=require('playwright');const fs=require('fs');
const S='fill="none" stroke="#7A1E2C" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"';
const cherry=`<svg viewBox="0 0 200 200"><path d="M100 30 C90 70 70 95 62 120 M100 30 C110 70 128 100 138 125" ${S}/><path d="M100 30 C120 18 150 22 162 40 C140 48 118 44 100 30Z" fill="#7A1E2C"/><circle cx="60" cy="148" r="34" fill="#B3263A"/><circle cx="140" cy="150" r="34" fill="#B3263A"/><path d="M46 136 a16 16 0 0 1 14 -10 M126 138 a16 16 0 0 1 14 -10" stroke="#F4EAE1" stroke-width="6" fill="none" stroke-linecap="round"/></svg>`;
const mirror=`<svg viewBox="0 0 200 200"><ellipse cx="100" cy="82" rx="52" ry="64" ${S}/><ellipse cx="100" cy="82" rx="38" ry="50" fill="#D9A7A0" opacity=".45"/><path d="M100 146 V188 M74 188 H126" ${S}/><path d="M80 62 l14 -14 M84 82 l26 -26" stroke="#F4EAE1" stroke-width="6" stroke-linecap="round"/></svg>`;
const collab=`<svg viewBox="0 0 200 200"><path d="M100 40 l10 30 30 10 -30 10 -10 30 -10 -30 -30 -10 30 -10Z" fill="#B3263A"/><path d="M152 118 l6 17 17 6 -17 6 -6 17 -6 -17 -17 -6 17 -6Z" fill="#7A1E2C"/><path d="M48 128 l5 14 14 5 -14 5 -5 14 -5 -14 -14 -5 14 -5Z" fill="#7A1E2C"/><path d="M40 60 l3 8 8 3 -8 3 -3 8 -3 -8 -8 -3 8 -3Z" fill="#D9A7A0"/></svg>`;
const martini=`<svg viewBox="0 0 200 200"><path d="M40 50 H160 L100 118Z" ${S}/><path d="M58 70 H142 L100 118Z" fill="#B3263A" opacity=".9"/><path d="M100 118 V180 M70 182 H130" ${S}/><circle cx="132" cy="44" r="15" fill="#B3263A"/><path d="M132 30 C136 18 146 12 154 10" ${S} stroke-width="5"/></svg>`;
const fork=`<svg viewBox="0 0 200 200"><circle cx="100" cy="110" r="66" ${S}/><circle cx="100" cy="110" r="46" fill="#D9A7A0" opacity=".45"/><path d="M28 40 V80 M18 40 V72 a10 10 0 0 0 20 0 V40 M28 80 V186" ${S} stroke-width="6" transform="translate(-6 0)"/><path d="M182 186 V40 C164 50 162 90 170 110 H182" ${S} stroke-width="6" transform="translate(4 0)"/></svg>`;
const covers=[
 ['me','me',220,'Maena',mirror],
 ['collabs','collabs',190,'Marques & co',collab],
 ['her','her',230,'Soirées & sorties',martini],
 ['becoming','becoming',165,'Becoming Her',cherry],
 ['annecy','à croquer',150,'Annecy',fork],
];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
const t=fs.readFileSync(__dirname+'/template.html','utf8');
for(const [f,w,s,tag,ic] of covers){await p.setContent(t.replace('__ICON__',ic).replace('__WORD__',w).replace('__SIZE__',s).replace('__TAG__',tag),{waitUntil:'networkidle'});
await p.evaluate(()=>document.fonts.ready);await p.screenshot({path:`${__dirname}/${f}.png`});}
await b.close();})();
