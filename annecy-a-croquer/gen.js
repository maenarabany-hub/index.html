// Visuels « Annecy à croquer » : node gen.js
// Ajoute un restaurant dans la liste, mets sa photo dans photos/<id>.jpg, relance.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const restos=[
 {id:'sanzaru', nom:'Sanzaru', titre:'Le brunch<br>qui vaut le réveil',
  plat:'[ton plat préféré]', lieu:'[adresse à confirmer]', prix:'[€ / €€ / €€€]',
  pour:'Brunch entre copines', avis:'[ton avis en une phrase]'},
];
const formats={
 post :{H:1350,PAD:70,T:84,AW:560,AH:520,FB:36,cards:''},
 story:{H:1920,PAD:230,T:104,AW:680,AH:700,FB:200,cards:''},
};
(async()=>{const b=await chromium.launch();const p=await b.newPage();
const t=fs.readFileSync(__dirname+'/template.html','utf8');fs.mkdirSync(__dirname+'/visuels',{recursive:true});
for(const r of restos){
 const ph=['jpg','jpeg','png','webp'].map(e=>`${__dirname}/photos/${r.id}.${e}`).find(fs.existsSync);
 const bg=ph?`url(data:image/${path.extname(ph).slice(1).replace('jpg','jpeg')};base64,${fs.readFileSync(ph).toString('base64')})`:'linear-gradient(160deg,#F2D3D1,#E8B0B0)';
 for(const [f,F] of Object.entries(formats)){
  let h=t;const rep={...F,PHOTO:bg,PHTXT:ph?'':'Ta photo ici',TITRE:r.titre,NOM:r.nom,PLAT:r.plat,LIEU:r.lieu,PRIX:r.prix,POUR:r.pour,AVIS:r.avis,CARDS:F.cards};
  for(const [k,v] of Object.entries(rep)) h=h.split(`__${k}__`).join(v);
  await p.setViewportSize({width:1080,height:F.H});await p.setContent(h,{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);
  await p.screenshot({path:`${__dirname}/visuels/${r.id}-${f}.png`});}}
await b.close();})();
