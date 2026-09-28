/* RKMS MediStock Pro - upgrade pack v2 (additive; original code untouched) */
(function(){
'use strict';
var $=function(s,c){return(c||document).querySelector(s)},$$=function(s,c){return Array.prototype.slice.call((c||document).querySelectorAll(s))};
function E(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
var brand=function(){return localStorage.getItem('ms_college')||'Ramakrishna Mission Health Center'};

var css=document.createElement('style');css.textContent=
'.chat-msg{white-space:pre-line}#rkChat{width:360px;max-height:540px}#rkChat .chat-body{max-height:360px}'+
'.page-header.rk-h{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}'+
'body.mode-midnight{--bg:#050816;--surface:#0B1229;--surface2:#131C3D;--surface3:#1E2A55;--text:#E8EEFF;--text2:#9FB0E0;--text3:#6B7BB0;--border:rgba(120,150,255,.12);--border2:rgba(120,150,255,.22)}'+
'body.mode-forest{--bg:#0B1710;--surface:#12241A;--surface2:#193324;--surface3:#234632;--text:#E6F4EA;--text2:#9CC5A8;--text3:#6E9A7C;--border:rgba(150,255,190,.1);--border2:rgba(150,255,190,.2)}'+
'body.mode-contrast{--bg:#000;--surface:#000;--surface2:#111;--surface3:#222;--text:#fff;--text2:#fff;--text3:#ddd;--border:rgba(255,255,255,.5);--border2:#fff}'+
'body.mode-sepia{--bg:#F4ECD8;--surface:#FBF5E6;--surface2:#F1E7CE;--surface3:#E8DBB8;--text:#3B2F1E;--text2:#6B5A3E;--text3:#9A8760;--border:rgba(90,60,20,.12);--border2:rgba(90,60,20,.22)}'+
'body.mode-ocean{--bg:#E6F2FA;--surface:#FFFFFF;--surface2:#F0F8FD;--surface3:#DCEBF5;--text:#0B2A3F;--text2:#3E6480;--text3:#7C9BB3}';
document.head.appendChild(css);

/* 13. Login: remove credential hint */
function loginFix(){var h=$('.login-hint');if(h)h.remove();var u=$('#lu');if(u){u.value='';u.autocomplete='off'}var p=$('#lp');if(p)p.autocomplete='new-password'}

/* 1. Category "Other" -> type your own */
function clearCustom(s){$$('option[data-custom]',s).forEach(function(o){o.remove()})}
function othOpt(s){return $$('option',s).filter(function(o){return o.value==='Other'})[0]||null}
function otherInput(id){
  var s=$('#'+id);if(!s)return;
  var i=document.createElement('input');i.type='text';i.className='form-control-m';i.placeholder='Type new category name';i.style.cssText='display:none;margin-top:6px';
  s.parentNode.appendChild(i);s._oi=i;
  s.addEventListener('change',function(){var o=s.options[s.selectedIndex];i.style.display=(s.value==='Other'||(o&&o.dataset.custom))?'block':'none';if(s.value==='Other')i.focus()});
  i.addEventListener('input',function(){
    clearCustom(s);var v=i.value.trim();
    if(!v){s.value='Other';return}
    var ex=$$('option',s).filter(function(o){return o.value.toLowerCase()===v.toLowerCase()&&o.value!=='Other'})[0];
    if(ex){s.value=ex.value;return}
    var o=new Option(v,v);o.dataset.custom='1';s.insertBefore(o,othOpt(s));s.value=v;
  });
}
function syncCats(){
  var cats=[];(window.meds||[]).forEach(function(m){if(m.cat&&cats.indexOf(m.cat)<0)cats.push(m.cat)});
  ['mc','em-c'].forEach(function(id){var s=$('#'+id);if(!s)return;
    cats.forEach(function(c){if(!$$('option',s).some(function(o){return o.value===c}))s.insertBefore(new Option(c,c),othOpt(s))})});
}
function resetOther(id){var s=$('#'+id);if(!s||!s._oi)return;s._oi.value='';s._oi.style.display='none';clearCustom(s);syncCats()}

/* 3/5. Phone: exactly 10 digits, neutral placeholders */
var PH={mn:'Enter medicine name',mbatch:'Enter batch number',mq:'Enter quantity',mm:'Enter minimum alert level',mprice:'Enter price per unit',mdose:'Enter dosage information',mnote:'Enter notes',
 dn:'Enter doctor name',dsp:'Enter specialization',ddays:'Enter available days',dtim:'Enter timing',sn:'Enter student name',sr:'Enter roll number',sd:'Enter department',sa:'Enter allergies (if any)',sadr:'Enter address',
 dnote:'Enter diagnosis / notes','nt-title':'Enter notice title','nt-by':'Enter your name','set-college':'Enter institution name',ds:'Type student name...'};
var PHONES=['dph','sp','sec2','es-p','es-ec'];
function phoneSetup(){
  Object.keys(PH).forEach(function(id){var e=$('#'+id);if(e)e.placeholder=PH[id]});
  PHONES.forEach(function(id){var e=$('#'+id);if(!e)return;e.maxLength=10;e.inputMode='numeric';e.pattern='[0-9]{10}';e.placeholder='Enter 10-digit mobile number';
    e.addEventListener('input',function(){var v=e.value.replace(/\D/g,'').slice(0,10);if(v!==e.value)e.value=v})});
}
function chk(ids,req){for(var i=0;i<ids.length;i++){var e=$('#'+ids[i]),v=e.value.trim();if((req&&!v)||(v&&!/^\d{10}$/.test(v))){alert('Phone number must be exactly 10 digits (numbers only).');e.focus();return false}}return true}
function wrap(n,pre,post){var o=window[n];if(typeof o!=='function')return;window[n]=function(){if(pre&&pre.apply(this,arguments)===false)return;var r=o.apply(this,arguments);if(post){if(r&&r.then)r.then(function(){post()});else post()}return r}}

/* 2,4-9. Export in many formats */
var F=[['csv','CSV','table_chart'],['xls','Excel (.xls)','grid_on'],['doc','Word (.doc)','description'],['pdf','PDF / Print','picture_as_pdf'],['json','JSON','data_object'],['txt','Text (.txt)','notes']];
var KEYS={medicines:'meds',doctors:'docs',students:'stus',dispense:'hist',prescription:'rx',history:'hist',daily:'daily',analytics:'ana',stockval:'stock',calendar:'cal',birthdays:'bday',noticeboard:'notes',actlog:'log'};
function todayH(){var t=new Date().toDateString();return(window.hist||[]).filter(function(h){try{return new Date(h.dtRaw).toDateString()===t}catch(e){return false}})}
function histRows(a){return a.map(function(h){return[h.studentName,h.roll,h.dept,h.year,h.medicine,h.qty,h.sched||'',h.doctor||'',h.note||'',h.dt]})}
var HH=['Student','Roll','Dept','Year','Medicine','Qty','Schedule','Doctor','Notes','Date'];
function DS(k){
  var meds=window.meds||[],stus=window.stus||[],docs=window.docs||[],hist=window.hist||[];
  switch(k){
  case'meds':return{t:'Medicine Inventory',h:['Name','Batch','Category','Stock','Min Alert','Price','Value','Dosage','Expiry','Status'],r:meds.map(function(m){return[m.name,m.batch||'',m.cat||'',m.qty,m.min,m.price||0,(m.qty*(m.price||0)).toFixed(2),m.dose||'',m.expiry||'',medSt(m).l]})};
  case'docs':return{t:'Doctor List',h:['Name','Specialization','Phone','Days','Timing'],r:docs.map(function(d){return[d.name,d.spec||'',d.phone||'',d.days||'',d.timing||'']})};
  case'stus':return{t:'Student List',h:['Name','Roll','Dept','Year','Blood','Phone','Emergency','Birthday','Allergy','Address','Visits'],r:stus.map(function(s){return[s.name,s.roll||'',s.dept||'',s.year||'',s.blood||'',s.phone||'',s.ec||'',s.bday||'',s.allergy||'',s.addr||'',hist.filter(function(h){return h.stuId===s.id}).length]})};
  case'hist':return{t:'Dispense History',h:HH,r:histRows(hist)};
  case'rx':return{t:'Prescriptions',h:['Date','Patient','Roll','Doctor','Diagnosis','Medicine','Qty','Dosage','Schedule'],r:hist.map(function(h){return[h.dt,h.studentName,h.roll,h.doctor||'',h.note||'',h.medicine,h.qty,h.dose||'',h.sched||'']})};
  case'daily':return{t:'Daily Report '+new Date().toLocaleDateString('en-IN'),h:HH,r:histRows(todayH())};
  case'ana':var a=[];[['Medicine',function(h){return h.medicine}],['Department',function(h){return h.dept||'-'}],['Year',function(h){return h.year||'-'}],['Month',function(h){var d=new Date(h.dtRaw);return isNaN(d)?'-':d.toLocaleString('en-IN',{month:'short',year:'numeric'})}]].forEach(function(g){var c={};hist.forEach(function(h){var x=g[1](h);c[x]=(c[x]||0)+h.qty});Object.keys(c).sort(function(p,q){return c[q]-c[p]}).forEach(function(x){a.push([g[0],x,c[x]])})});return{t:'Analytics',h:['Type','Item','Total Qty'],r:a};
  case'stock':var tot=0;var r=meds.map(function(m){var v=m.qty*(m.price||0);tot+=v;return[m.name,m.cat||'',m.qty,m.price||0,v.toFixed(2),medSt(m).l]});if(r.length)r.push(['TOTAL','','','',tot.toFixed(2),'']);return{t:'Stock Value',h:['Medicine','Category','Stock','Price/Unit','Total Value','Status'],r:r};
  case'cal':return{t:'Calendar '+(window.calMonth+1)+'-'+window.calYear,h:['Date','Student','Medicine','Qty'],r:hist.filter(function(h){var d=new Date(h.dtRaw);return d.getFullYear()===window.calYear&&d.getMonth()===window.calMonth}).map(function(h){return[new Date(h.dtRaw).toLocaleDateString('en-IN'),h.studentName,h.medicine,h.qty]})};
  case'bday':return{t:'Birthdays',h:['Name','Roll','Dept','Birthday','Days Left'],r:stus.filter(function(s){return s.bday}).map(function(s){return[s.name,s.roll||'',s.dept||'',s.bday,getBdayLeft(s.bday)]}).sort(function(a,b){return a[4]-b[4]})};
  case'notes':return{t:'Notice Board',h:['Title','Message','Posted By','Time','Colour'],r:(window.notices||[]).map(function(n){return[n.title,n.msg,n.by||'',n.time,n.color]})};
  case'log':return{t:'Activity Log',h:['Time','Type','Action'],r:(window.log||[]).map(function(l){return[l.time,l.type,String(l.msg).replace(/<[^>]*>/g,'')]})};
  }
}
function save(name,mime,txt){var b=new Blob([txt],{type:mime}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(a.href);a.remove()},500)}
function html(d,fmt){
  var x=fmt==='xls'?' xmlns:x="urn:schemas-microsoft-com:office:excel"':'';
  return'<html xmlns:o="urn:schemas-microsoft-com:office:office"'+x+'><head><meta charset="utf-8"><title>'+E(d.t)+'</title><style>body{font-family:Arial}table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:5px 8px;font:12px Arial;text-align:left}th{background:#1D9E75;color:#fff}</style></head><body><h2>'+E(brand())+'</h2><h3>'+E(d.t)+' - '+new Date().toLocaleDateString('en-IN')+'</h3><table><tr>'+d.h.map(function(h){return'<th>'+E(h)+'</th>'}).join('')+'</tr>'+d.r.map(function(r){return'<tr>'+r.map(function(c){return'<td>'+E(c)+'</td>'}).join('')+'</tr>'}).join('')+'</table></body></html>';
}
function exportAs(k,f){
  var d=DS(k);if(!d||!d.r.length){alert('No data to export');return}
  var n='RKMS_'+d.t.replace(/\W+/g,'_')+'_'+new Date().toISOString().slice(0,10);
  if(f==='csv')save(n+'.csv','text/csv;charset=utf-8','\ufeff'+[d.h].concat(d.r).map(function(r){return r.map(function(c){return'"'+String(c).replace(/"/g,'""')+'"'}).join(',')}).join('\r\n'));
  else if(f==='json')save(n+'.json','application/json',JSON.stringify(d.r.map(function(r){var o={};d.h.forEach(function(h,i){o[h]=r[i]});return o}),null,2));
  else if(f==='txt')save(n+'.txt','text/plain;charset=utf-8',[d.h].concat(d.r).map(function(r){return r.join('\t')}).join('\n'));
  else if(f==='xls')save(n+'.xls','application/vnd.ms-excel',html(d,'xls'));
  else if(f==='doc')save(n+'.doc','application/msword',html(d,'doc'));
  else{var fr=document.createElement('iframe');fr.style.cssText='position:fixed;width:0;height:0;border:0';document.body.appendChild(fr);var w=fr.contentWindow.document;w.open();w.write(html(d,'pdf'));w.close();setTimeout(function(){fr.contentWindow.focus();fr.contentWindow.print();setTimeout(function(){fr.remove()},2500)},300)}
  if(window.toast)toast('Exported '+d.t+' as '+f.toUpperCase(),'success');
}
var curKey=null;
function exportUI(){
  var m=document.createElement('div');m.className='modal-overlay';m.id='rk-exp';
  m.innerHTML='<div class="modal-box" style="max-width:420px"><div class="modal-header"><div class="modal-title"><span class="material-icons-round">download</span> Export</div><button class="modal-close" onclick="closeModal(\'rk-exp\')"><span class="material-icons-round">close</span></button></div><div class="mbtn-group">'+F.map(function(f){return'<button class="mbtn" data-rkf="'+f[0]+'"><span class="material-icons-round">'+f[2]+'</span> '+f[1]+'</button>'}).join('')+'</div></div>';
  document.body.appendChild(m);
  Object.keys(KEYS).forEach(function(sec){var h=$('#sec-'+sec+' .page-header');if(!h)return;var d=document.createElement('div');while(h.firstChild)d.appendChild(h.firstChild);h.appendChild(d);h.classList.add('rk-h');
    var b=document.createElement('button');b.className='mbtn primary sm';b.dataset.rkExp=KEYS[sec];b.innerHTML='<span class="material-icons-round">download</span> Export';h.appendChild(b)});
  document.addEventListener('click',function(e){var b=e.target.closest('[data-rk-exp]');if(b){curKey=b.dataset.rkExp;openModal('rk-exp');return}
    var f=e.target.closest('[data-rkf]');if(f){closeModal('rk-exp');exportAs(curKey,f.dataset.rkf)}});
}

/* 10. Display modes */
var DARKS=['dark','midnight','forest','contrast'];
var MODES=[['light','☀️ Light'],['dark','🌙 Dark'],['system','🖥️ System'],['midnight','🌌 Midnight'],['forest','🌲 Forest'],['sepia','📜 Sepia'],['ocean','🌊 Ocean'],['contrast','⚫ High Contrast']];
function setMode(m){
  localStorage.setItem('rk_mode',m);
  var r=m==='system'?(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'):m,b=document.body,isD=DARKS.indexOf(r)>-1;
  b.className=b.className.replace(/\bmode-\S+/g,'').trim();b.classList.toggle('dark-mode',isD);if(r!=='light'&&r!=='dark')b.classList.add('mode-'+r);
  localStorage.setItem('ms_dark',isD);window.dark=isD;
  var i=$('#darkico'),l=$('#darklbl');if(i)i.textContent=isD?'light_mode':'dark_mode';if(l)l.textContent=isD?'Light Mode':'Dark Mode';
  var s=$('#rk-mode');if(s)s.value=m;
}

/* 11. Languages (English, Tamil, Telugu, Hindi) */
var DICT={};function D(k,a,b,c){DICT[k]={ta:a,te:b,hi:c}}
D('Main','முதன்மை','ప్రధాన','मुख्य');D('Students','மாணவர்கள்','విద్యార్థులు','छात्र');D('Reports','அறிக்கைகள்','నివేదికలు','रिपोर्ट');D('Extras','கூடுதல்','అదనపు','अतिरिक्त');
D('Dashboard','டாஷ்போர்டு','డాష్‌బోర్డ్','डैशबोर्ड');D('Medicines','மருந்துகள்','మందులు','दवाइयाँ');D('Doctors','மருத்துவர்கள்','వైద్యులు','डॉक्टर');
D('Dispense','வழங்கல்','పంపిణీ','वितरण');D('Prescription','மருந்துச்சீட்டு','ప్రిస్క్రిప్షన్','पर्चा');D('History','வரலாறு','చరిత్ర','इतिहास');
D('Daily Report','தின அறிக்கை','రోజువారీ నివేదిక','दैनिक रिपोर्ट');D('Analytics','பகுப்பாய்வு','విశ్లేషణ','विश्लेषण');D('Stock Value','இருப்பு மதிப்பு','స్టాక్ విలువ','स्टॉक मूल्य');
D('Calendar','நாட்காட்டி','క్యాలెండర్','कैलेंडर');D('Birthdays','பிறந்தநாள்','పుట్టినరోజులు','जन्मदिन');D('Notice Board','அறிவிப்புப் பலகை','నోటీసు బోర్డు','सूचना पट');
D('Activity Log','செயல்பாட்டுப் பதிவு','కార్యకలాప లాగ్','गतिविधि लॉग');D('Settings','அமைப்புகள்','సెట్టింగ్‌లు','सेटिंग्स');D('Logout','வெளியேறு','లాగ్అవుట్','लॉगआउट');
D('Backup / Restore','காப்பு / மீட்பு','బ్యాకప్ / రీస్టోర్','बैकअप / रिस्टोर');D('Dispense Medicine','மருந்து வழங்கு','మందు పంపిణీ','दवा वितरण');
D('Dispense History','வழங்கிய வரலாறு','పంపిణీ చరిత్ర','वितरण इतिहास');D('Calendar View','நாட்காட்டி காட்சி','క్యాలెండర్ వీక్షణ','कैलेंडर दृश्य');
D('Birthday Tracker','பிறந்தநாள் கண்காணிப்பு','పుట్టినరోజు ట్రాకర్','जन्मदिन ट्रैकर');D('Add Medicine','மருந்து சேர்','మందు జోడించు','दवा जोड़ें');
D('Add Doctor','மருத்துவர் சேர்','వైద్యుడిని జోడించు','डॉक्टर जोड़ें');D('Add Student','மாணவர் சேர்','విద్యార్థిని జోడించు','छात्र जोड़ें');
D('Inventory','இருப்புப் பட்டியல்','ఇన్వెంటరీ','सूची');D('Doctor List','மருத்துவர் பட்டியல்','వైద్యుల జాబితా','डॉक्टर सूची');D('Student List','மாணவர் பட்டியல்','విద్యార్థుల జాబితా','छात्र सूची');
D('Search Student','மாணவரைத் தேடு','విద్యార్థిని వెతకండి','छात्र खोजें');D('Dispense All','அனைத்தையும் வழங்கு','అన్నీ పంపిణీ చేయి','सभी वितरित करें');
D('Post Notice','அறிவிப்பை இடு','నోటీసు పోస్ట్ చేయి','सूचना पोस्ट करें');D('Save','சேமி','సేవ్','सहेजें');D('Cancel','ரத்து','రద్దు','रद्द करें');
D('Export','ஏற்றுமதி','ఎగుమతి','निर्यात');D('Name','பெயர்','పేరు','नाम');D('Category','வகை','వర్గం','श्रेणी');D('Stock','இருப்பு','స్టాక్','स्टॉक');
D('Price','விலை','ధర','मूल्य');D('Expiry','காலாவதி','గడువు','समाप्ति');D('Status','நிலை','స్థితి','स्थिति');D('Actions','செயல்கள்','చర్యలు','कार्रवाई');
D('Phone','தொலைபேசி','ఫోన్','फ़ोन');D('Specialization','சிறப்பு','ప్రత్యేకత','विशेषज्ञता');
var REV={};Object.keys(DICT).forEach(function(k){['ta','te','hi'].forEach(function(l){REV[DICT[k][l]]=k})});
var store=new WeakMap(),lang='en',obs,tmr;
function trText(b){
  var lead=b.match(/^[\s\p{Extended_Pictographic}\uFE0F₹]*/u)[0],trail=b.match(/\s*$/)[0],rest=b.slice(lead.length,b.length-trail.length);if(!rest)return b;
  var k=REV[rest]||rest,d=DICT[k];if(!d)return b;return lead+(lang==='en'?k:d[lang])+trail;
}
function applyLang(){
  if(obs)obs.disconnect();
  var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null),n;
  while((n=w.nextNode())){var p=n.parentNode;if(!p||/^(SCRIPT|STYLE|TEXTAREA|OPTION)$/.test(p.nodeName)||(p.classList&&p.classList.contains('material-icons-round'))||(p.closest&&p.closest('#rkChat')))continue;
    var cur=n.nodeValue,rec=store.get(n),base=(rec&&cur===rec.t)?rec.o:cur,out=trText(base);if(out!==cur){n.nodeValue=out;store.set(n,{o:base,t:out})}}
  document.documentElement.lang=lang;
  if(obs)obs.observe(document.body,{childList:true,subtree:true,characterData:true});
}
function setLang(l){lang=l;localStorage.setItem('rk_lang',l);var s=$('#rk-lang');if(s)s.value=l;applyLang()}

/* 12. Smart assistant - answers from live dashboard data */
var TABKW=[['stock value','stockval'],['prescription','prescription'],['daily','daily'],['analytic','analytics'],['calendar','calendar'],['birthday','birthdays'],['notice','noticeboard'],['activity','actlog'],['history','history'],['dispense','dispense'],['doctor','doctors'],['student','students'],['medicine','medicines'],['inventory','medicines'],['dashboard','dashboard']];
function L(a,f,n){n=n||10;return a.slice(0,n).map(f).join('\n')+(a.length>n?'\n...and '+(a.length-n)+' more':'')}
function dLeft(m){return m.expiry?Math.ceil((new Date(m.expiry)-new Date())/864e5):null}
function inDays(n){var t=Date.now()-n*864e5;return(window.hist||[]).filter(function(h){return new Date(h.dtRaw).getTime()>=t})}
function topBy(a,f){var c={};a.forEach(function(h){var k=f(h);c[k]=(c[k]||0)+h.qty});return Object.keys(c).sort(function(x,y){return c[y]-c[x]}).map(function(k){return[k,c[k]]})}
function summary(){
  var meds=window.meds||[],td=todayH(),low=meds.filter(function(m){return m.qty>0&&m.qty<=m.min}).length,out=meds.filter(function(m){return m.qty===0}).length,
  ex=meds.filter(function(m){var d=dLeft(m);return d!==null&&d>=0&&d<=30}).length,exd=meds.filter(function(m){var d=dLeft(m);return d!==null&&d<0}).length,
  val=meds.reduce(function(s,m){return s+m.qty*(m.price||0)},0),u={};td.forEach(function(h){u[h.stuId]=1});
  return'Today: '+td.length+' dispense record(s), '+Object.keys(u).length+' student(s)\nMedicines: '+meds.length+' | Low: '+low+' | Out: '+out+' | Expiring 30d: '+ex+' | Expired: '+exd+'\nStudents: '+(window.stus||[]).length+' | Doctors: '+(window.docs||[]).length+' | Notices: '+(window.notices||[]).length+'\nStock value: Rs.'+val.toFixed(2);
}
function answer(raw){
  var q=raw.toLowerCase().trim(),tok=q.split(/[^a-z0-9+\-]+/).filter(Boolean),meds=window.meds||[],stus=window.stus||[],docs=window.docs||[],hist=window.hist||[],m;
  if(/^(hi|hello|hey|hai|vanakkam|namaste)\b/.test(q))return'Hello! Ask me about stock, expiry, students, doctors, birthdays, today\'s dispensing, analytics, notices... or type "help".';
  if(/^(open|go to|goto|take me to|navigate|show me the)\b/.test(q)){for(var i=0;i<TABKW.length;i++)if(q.indexOf(TABKW[i][0])>-1){showTab(TABKW[i][1]);return'Opening '+TABKW[i][1]+'...'}}
  if(/^help|what can you/.test(q))return'Try:\n- "summary" / "alerts"\n- "low stock", "out of stock", "expiring soon", "expired"\n- a medicine name (stock, price, expiry)\n- a student name or roll no. (profile)\n- "today", "top medicine", "frequent visitors"\n- "birthdays", "blood group o+", "allergies"\n- "categories", "doctors", "notices", "activity log"\n- "stock value", "this week / month"\n- "open history" (go to any tab)';
  var med=meds.filter(function(x){var n=x.name.toLowerCase();return q.indexOf(n)>-1||n.split(/[\s\d.\/\-]+/).some(function(w){return w.length>3&&tok.indexOf(w)>-1})})[0];
  if(med){var d=dLeft(med);return med.name+'\nStock: '+med.qty+' (min '+med.min+') - '+medSt(med).l+'\nCategory: '+(med.cat||'-')+' | Batch: '+(med.batch||'-')+'\nPrice: Rs.'+(med.price||0)+' | Value: Rs.'+(med.qty*(med.price||0)).toFixed(2)+'\nExpiry: '+(med.expiry||'-')+(d!==null?' ('+(d<0?'expired':d+' days left')+')':'')+'\nDosage: '+(med.dose||'-')}
  var stu=stus.filter(function(s){var n=(s.name||'').toLowerCase();return q.indexOf(n)>-1||(s.roll&&tok.indexOf(s.roll.toLowerCase())>-1)||n.split(/\s+/).some(function(w){return w.length>3&&tok.indexOf(w)>-1})});
  if(stu.length){return stu.slice(0,3).map(function(s){var h=hist.filter(function(x){return x.stuId===s.id});return s.name+' ('+(s.roll||'-')+')\n'+[s.dept,s.year,s.blood].filter(Boolean).join(' | ')+'\nPhone: '+(s.phone||'-')+' | Emergency: '+(s.ec||'-')+'\nAllergy: '+(s.allergy||'none')+' | Birthday: '+(s.bday||'-')+'\nVisits: '+h.length+(h.length?'\nLast: '+h[0].medicine+' on '+h[0].dt:'')}).join('\n\n')}
  var doc=docs.filter(function(d){var n=d.name.toLowerCase();return q.indexOf(n)>-1||n.split(/[\s.]+/).some(function(w){return w.length>3&&tok.indexOf(w)>-1})})[0];
  if(doc)return doc.name+'\n'+(doc.spec||'-')+'\nPhone: '+(doc.phone||'-')+'\nDays: '+(doc.days||'-')+' | Timing: '+(doc.timing||'-');
  if(/out of stock|no stock|finished/.test(q)){var o=meds.filter(function(x){return x.qty===0});return o.length?'Out of stock ('+o.length+'):\n'+L(o,function(x){return'- '+x.name}):'Nothing is out of stock.'}
  if(/low|kammi|running out|reorder|restock/.test(q)){var lw=meds.filter(function(x){return x.qty>0&&x.qty<=x.min});return lw.length?'Low stock ('+lw.length+'):\n'+L(lw,function(x){return'- '+x.name+': '+x.qty+' (min '+x.min+')'}):'No low stock items.'}
  if(/expired/.test(q)){var e=meds.filter(function(x){var d=dLeft(x);return d!==null&&d<0});return e.length?'Expired ('+e.length+'):\n'+L(e,function(x){return'- '+x.name+' ('+x.expiry+')'}):'No expired medicines.'}
  if(/expir/.test(q)){var s=meds.filter(function(x){var d=dLeft(x);return d!==null&&d>=0&&d<=30});return s.length?'Expiring within 30 days ('+s.length+'):\n'+L(s,function(x){return'- '+x.name+' - '+x.expiry+' ('+dLeft(x)+'d)'}):'Nothing expires in the next 30 days.'}
  if(/stock value|worth|total value|inventory value/.test(q))return'Total stock value: Rs.'+meds.reduce(function(s,x){return s+x.qty*(x.price||0)},0).toFixed(2);
  if(/summary|overview|alert|status|report|dashboard/.test(q))return summary();
  if(/categor/.test(q)){var cat=meds.filter(function(x){return x.cat&&q.indexOf(x.cat.toLowerCase())>-1});if(cat.length)return cat[0].cat+' ('+cat.length+'):\n'+L(cat,function(x){return'- '+x.name+': '+x.qty});var c={};meds.forEach(function(x){var k=x.cat||'Uncategorised';c[k]=(c[k]||0)+1});return Object.keys(c).length?'Categories:\n'+Object.keys(c).map(function(k){return'- '+k+': '+c[k]}).join('\n'):'No medicines yet.'}
  if(/birthday|bday|pirandha/.test(q)){var b=stus.filter(function(x){return x.bday}).map(function(x){return{n:x.name,d:getBdayLeft(x.bday),b:x.bday}}).sort(function(a,b){return a.d-b.d});if(/month/.test(q)){var mo=new Date().getMonth();b=b.filter(function(x){return new Date(x.b).getMonth()===mo})}else b=b.filter(function(x){return x.d<=7});return b.length?'Birthdays:\n'+L(b,function(x){return'- '+x.n+' - '+(x.d===0?'TODAY':x.d+' day(s)')}):'No birthdays in that period.'}
  if(m=q.match(/\b(ab|a|b|o)\s*(\+|-|positive|negative|pos|neg)/)){var bg=m[1].toUpperCase()+(/^(\+|positive|pos)/.test(m[2])?'+':'-'),bs=stus.filter(function(x){return x.blood===bg});return bs.length?'Blood group '+bg+' ('+bs.length+'):\n'+L(bs,function(x){return'- '+x.name+' '+(x.phone||'')}):'No students with '+bg+'.'}
  if(/allerg/.test(q)){var al=stus.filter(function(x){return x.allergy});return al.length?'Students with allergies:\n'+L(al,function(x){return'- '+x.name+': '+x.allergy}):'No allergies recorded.'}
  if(/frequent|regular|most visit/.test(q)){var v={};hist.forEach(function(h){v[h.studentName]=(v[h.studentName]||0)+1});var f=Object.keys(v).sort(function(a,b){return v[b]-v[a]}).slice(0,5);return f.length?'Frequent visitors:\n'+f.map(function(k){return'- '+k+': '+v[k]+' visits'}).join('\n'):'No visits yet.'}
  if(/top|most|popular|highest/.test(q)&&/medicine|used|dispens|dept|department|year/.test(q)){var t=/dept|department/.test(q)?topBy(hist,function(h){return h.dept||'-'}):topBy(hist,function(h){return h.medicine});return t.length?'Top 5:\n'+t.slice(0,5).map(function(x,i){return(i+1)+'. '+x[0]+' - '+x[1]}).join('\n'):'No dispense data yet.'}
  if(/today|innaiku/.test(q)){var td=todayH();return td.length?'Today ('+td.length+'):\n'+L(td,function(h){return'- '+h.studentName+': '+h.medicine+' x'+h.qty}):'No dispensing recorded today.'}
  if(/week|month|last \d+ day/.test(q)){var n=/week/.test(q)?7:(m=q.match(/last (\d+) day/))?+m[1]:30,r=inDays(n);return'Last '+n+' days: '+r.length+' record(s), '+r.reduce(function(s,h){return s+h.qty},0)+' units.'+(r.length?'\nTop: '+topBy(r,function(h){return h.medicine}).slice(0,3).map(function(x){return x[0]+' ('+x[1]+')'}).join(', '):'')}
  if(/how many|count|total|evlo|number/.test(q)){if(/student/.test(q))return stus.length+' students registered.';if(/doctor/.test(q))return docs.length+' doctors.';if(/notice/.test(q))return(window.notices||[]).length+' notices.';if(/dispens|record|history/.test(q))return hist.length+' dispense records.';return meds.length+' medicines in inventory.'}
  if(/doctor/.test(q))return docs.length?'Doctors:\n'+L(docs,function(d){return'- '+d.name+(d.spec?' ('+d.spec+')':'')+' '+(d.timing||'')}):'No doctors added.';
  if(/dept|department/.test(q)){var dc={};stus.forEach(function(s){var k=s.dept||'-';dc[k]=(dc[k]||0)+1});return Object.keys(dc).map(function(k){return'- '+k+': '+dc[k]}).join('\n')||'No students yet.'}
  if(/notice|announce/.test(q)){var nt=window.notices||[];return nt.length?'Latest notices:\n'+L(nt,function(n){return'- '+n.title+': '+n.msg},5):'No notices.'}
  if(/log|activity/.test(q)){var lg=window.log||[];return lg.length?'Recent activity:\n'+L(lg,function(l){return'- '+l.time+': '+String(l.msg).replace(/<[^>]*>/g,'')},6):'No activity yet.'}
  if(/student/.test(q))return stus.length+' students registered. Type a student name or roll number for details.';
  if(/medicine|stock|inventory/.test(q))return meds.length+' medicines in inventory. Ask "low stock", "expiring soon" or a medicine name.';
  return'I could not find that in your data. Try a medicine, student or doctor name, or type "help".';
}
function chatUI(){
  $$('.chat-fab,#chatPanel').forEach(function(e){e.remove()});
  var fab=document.createElement('button');fab.className='chat-fab';fab.title='RKMS Assistant';fab.innerHTML='<span class="material-icons-round">smart_toy</span>';
  var p=document.createElement('div');p.className='chat-panel';p.id='rkChat';
  p.innerHTML='<div class="chat-head"><span>RKMS Assistant</span><span class="material-icons-round cclose" id="rkcx">close</span></div><div class="chat-body" id="rkcb"><div class="chat-msg bot">Hi! I read live data from this dashboard. Ask anything - stock, expiry, students, doctors, birthdays, reports. Type "help" for examples.</div></div><div class="chat-quick">'+['Summary','Low stock','Expiring soon','Today','Top medicine','Birthdays','Help'].map(function(x){return'<span data-q="'+x+'">'+x+'</span>'}).join('')+'</div><div class="chat-input-wrap"><input type="text" id="rkci" placeholder="Ask about anything..."><button id="rkcs"><span class="material-icons-round">send</span></button></div>';
  document.body.appendChild(fab);document.body.appendChild(p);
  function add(t,w){var d=document.createElement('div');d.className='chat-msg '+w;d.textContent=t;$('#rkcb').appendChild(d);$('#rkcb').scrollTop=1e9}
  function send(t){var i=$('#rkci');t=(t||i.value).trim();if(!t)return;i.value='';add(t,'user');var a;try{a=answer(t)}catch(e){a='Sorry, I could not read the data. Please login and try again.'}setTimeout(function(){add(a,'bot')},200)}
  fab.onclick=function(){p.classList.toggle('show')};$('#rkcx').onclick=function(){p.classList.remove('show')};
  $('#rkcs').onclick=function(){send()};$('#rkci').addEventListener('keydown',function(e){if(e.key==='Enter')send()});
  $$('.chat-quick span',p).forEach(function(s){s.onclick=function(){send(s.dataset.q)}});
}

function init(){
  loginFix();phoneSetup();otherInput('mc');otherInput('em-c');syncCats();exportUI();chatUI();
  var lt=$('.lang-toggle-btn');if(lt)lt.remove();
  var f=$('.sidebar-footer'),w=document.createElement('div');w.style.cssText='display:flex;gap:6px;padding:4px 6px 8px';
  w.innerHTML='<select id="rk-mode" class="form-control-m" style="padding:6px;font-size:12px" title="Display mode">'+MODES.map(function(x){return'<option value="'+x[0]+'">'+x[1]+'</option>'}).join('')+'</select><select id="rk-lang" class="form-control-m" style="padding:6px;font-size:12px" title="Language"><option value="en">English</option><option value="ta">தமிழ்</option><option value="te">తెలుగు</option><option value="hi">हिन्दी</option></select>';
  f.insertBefore(w,f.firstChild);
  $('#rk-mode').onchange=function(e){setMode(e.target.value)};$('#rk-lang').onchange=function(e){setLang(e.target.value)};
  window.toggleDark=function(){setMode(document.body.classList.contains('dark-mode')?'light':'dark')};
  matchMedia('(prefers-color-scheme:dark)').addEventListener('change',function(){if(localStorage.getItem('rk_mode')==='system')setMode('system')});
  wrap('buildPills',null,syncCats);
  wrap('openEditMed',null,function(){var s=$('#em-c');if(!s)return;clearCustom(s);if(s._oi){s._oi.value='';s._oi.style.display='none'}syncCats();var m=(window.meds||[]).filter(function(x){return x.id===window.editMedId})[0];if(m&&m.cat)s.value=m.cat});
  wrap('addMed',null,function(){if(!$('#mn').value)resetOther('mc')});
  wrap('addDoctor',function(){return chk(['dph'],true)});
  wrap('addStudent',function(){return chk(['sp','sec2'])});
  wrap('saveEditStu',function(){return chk(['es-p','es-ec'])});
  wrap('saveEditMed',null,function(){resetOther('em-c')});
  setMode(localStorage.getItem('rk_mode')||(localStorage.getItem('ms_dark')==='true'?'dark':'light'));
  localStorage.removeItem('ms_lang');
  obs=new MutationObserver(function(){clearTimeout(tmr);tmr=setTimeout(applyLang,150)});
  setLang(localStorage.getItem('rk_lang')||'en');
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
