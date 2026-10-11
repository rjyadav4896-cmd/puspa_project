'use strict';
const $ = (selector) => document.querySelector(selector);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e = escapeHtml;
let csrf = '', page = 'dashboard', data = {}, formAction = null;
const meta = {
 dashboard:['Overview','Health centre overview','A little more connected. A lot more cared for.','New appointment'],
 students:['Students','Every student, connected','Student profiles, contact details, and important health information.','Add student'],
 appointments:['Appointments','Make time for care','Book a visit and keep every consultation on track.','New appointment'],
 doctors:['Doctors','Your campus care team','The people looking after your students.','Add doctor'],
 prescriptions:['Prescriptions','Clear guidance. Better care.','Consultation summaries and dispensed medicines in one place.','New prescription'],
 medicines:['Medicines','A well-stocked health centre','Monitor supplies, expiry dates, and medicine availability.','Add medicine'],
 records:['Health records','A fuller picture of health','Flexible healthcare notes with searchable tags.','Add health record'],
 analytics:['Analytics','Turn records into insights','Understand campus visits, care demand, and medicine use.',null]
};
async function api(path, method='GET', body) {
 const response = await fetch('/api/'+path, {method, headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, ...(body===undefined?{}:{body:JSON.stringify(body)})});
 const result = await response.json().catch(()=>({error:'The server returned an unexpected response.'}));
 if (!response.ok) {if(response.status===401 && path!=='login') await showLogin(); throw new Error(result.error||'Unable to complete this request.');}
 return result;
}
function toast(message) {$('#toast').textContent=message; $('#toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('#toast').hidden=true,4500);}
async function showLogin(){const current=await api('session');csrf=current.csrf;$('#workspace').hidden=true;$('#login-view').hidden=false;}
async function refresh(){
 const names=['students','doctors','appointments','prescriptions','medicines','records','analytics'];
 const results=await Promise.all(names.map(name=>api(name)));
 data=Object.fromEntries(names.map((name,index)=>[name,results[index]]));
 $('#store-mode').textContent='SQLite + '+data.analytics.document_store;
 render();
}
function person(name,subtitle=''){return `<div class="person"><span class="avatar">${e(name.replace(/^Dr\. /,'').split(' ').map(p=>p[0]).slice(0,2).join(''))}</span><div><strong>${e(name)}</strong><small>${e(subtitle)}</small></div></div>`;}
function badge(status){return `<span class="badge ${e(status.toLowerCase())}">${e(status)}</span>`;}
function dateTime(value){return new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'});}
function table(headings,rows){return rows.length?`<div class="table-wrap"><table><thead><tr>${headings.map(h=>`<th>${e(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`:'<div class="empty">No records to show yet.<br>Add a record to get started.</div>';}
function panel(title,subtitle,body,action=''){return `<section class="panel"><div class="panel-heading"><div><h3>${e(title)}</h3>${subtitle?`<p>${e(subtitle)}</p>`:''}</div>${action}</div>${body}</section>`;}
function bars(items,label,value){const max=Math.max(1,...items.map(i=>i[value]));return `<div class="chart-body">${items.length?items.map(i=>`<div class="bar-row"><span>${e(i[label])}</span><div class="bar-track"><div class="bar" data-width="${100*i[value]/max}"></div></div><strong>${e(i[value])}</strong></div>`).join(''):'<p class="empty">Insights will appear as records are added.</p>'}</div>`;}
function applyBars(){document.querySelectorAll('[data-width]').forEach(bar=>bar.style.width=bar.dataset.width+'%');}
function appointmentRows(items,actions=false){return items.map(a=>`<tr><td>${person(a.student_name,a.student_number)}</td><td>${e(a.doctor_name)}<small>${e(a.specialty)}</small></td><td>${e(dateTime(a.scheduled_at))}<small>${e(a.reason)}</small></td><td>${badge(a.status)}</td>${actions?`<td>${a.status==='Scheduled'?`<button class="action-button" data-status="Completed" data-id="${a.id}">Complete</button><button class="action-button" data-status="Cancelled" data-id="${a.id}">Cancel</button>`:'—'}</td>`:''}</tr>`);}
function alerts(){const today=new Date();const localDate=`${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;return data.medicines.filter(m=>m.stock<=m.reorder_level||m.expiry_date<localDate);}
function dashboard(){
 const totals=data.analytics.totals;
 const upcoming=data.appointments.filter(a=>a.status==='Scheduled').sort((a,b)=>a.scheduled_at.localeCompare(b.scheduled_at)).slice(0,5);
 return `<div class="welcome"><div><span class="eyebrow">CARE, WITH A CAMPUS COMMUNITY AT HEART</span><h2>Small check-ins. Healthier days.</h2><p>Your daily view of student health, upcoming visits, and the supplies that keep your care team ready.</p></div><div class="welcome-art" aria-hidden="true">✚</div></div>
 <div class="stats">${[['Registered students',totals.students,'Across your campus','♧'],["Today's appointments",totals.today,'All active visits today','▦'],['Scheduled visits',totals.scheduled,'Awaiting consultation','◷'],['Inventory alerts',totals.alerts,'Low stock or expired','⊞']].map(([label,value,note,icon])=>`<div class="stat"><div class="stat-top">${label}<span class="stat-icon">${icon}</span></div><strong>${value}</strong><small>${note}</small></div>`).join('')}</div>
 <div class="columns">${panel('Scheduled appointments','Keep the next consultation in view',table(['Student','Doctor','Visit','Status'],appointmentRows(upcoming)), '<button class="text-button" data-page="appointments">View all →</button>')}${panel('Inventory needs attention',`${alerts().length} medicines to review`,alerts().map(m=>`<div class="inventory-item"><div class="inventory-label"><span class="inventory-icon">⊞</span><div>${e(m.name)}<small>Reorder at ${m.reorder_level} · Expires ${e(m.expiry_date)}</small></div></div><span class="badge alert">${m.stock} ${e(m.unit)}</span></div>`).join('')||'<div class="empty">Your medicine supplies look healthy.</div>')}</div>
 <div class="columns">${panel('Care across departments','Non-cancelled visits · All time',bars(data.analytics.departments,'department','visits'))}${panel('A few helpful shortcuts','Less admin. More time for students.',`<div class="quick-grid"><button data-create="students"><span>♧</span>Add student</button><button data-create="records"><span>▧</span>Health note</button><button data-page="analytics"><span>▥</span>View insights</button></div>`)}</div>`;
}
function renderList(query=''){
 const items=(data[page]||[]).filter(item=>JSON.stringify(item).toLowerCase().includes(query.toLowerCase()));
 let body='';
 if(page==='students') body=table(['Student','Department','Blood group','Allergies','Profile'],items.map(s=>`<tr><td>${person(s.name,s.student_number)}<small>${e(s.email)}</small></td><td>${e(s.department)}</td><td>${badge(s.blood_group)}</td><td>${e(s.allergies||'None recorded')}</td><td><button class="action-button" data-profile="${s.id}">View history</button><button class="action-button" data-edit="students" data-id="${s.id}">Edit</button></td></tr>`));
 if(page==='doctors') body=table(['Doctor','Specialty','Email','Active visits','Action'],items.map(d=>`<tr><td>${person(d.name)}</td><td>${e(d.specialty)}</td><td>${e(d.email)}</td><td>${data.appointments.filter(a=>a.doctor_id===d.id&&a.status==='Scheduled').length}</td><td><button class="action-button" data-edit="doctors" data-id="${d.id}">Edit</button></td></tr>`));
 if(page==='appointments') body=table(['Student','Doctor','Visit','Status','Actions'],appointmentRows(items,true));
 if(page==='medicines') body=table(['Medicine / batch','Stock','Reorder level','Expires','Action'],items.map(m=>`<tr><td><strong>${e(m.name)}</strong></td><td>${alerts().some(a=>a.id===m.id)?`<span class="badge alert">${m.stock} ${e(m.unit)}</span>`:`${m.stock} ${e(m.unit)}`}</td><td>${m.reorder_level}</td><td>${e(m.expiry_date)}</td><td><button class="action-button" data-restock="${m.id}">Restock</button></td></tr>`));
 if(page==='records') body=`<div class="record-grid">${items.map(r=>`<article class="record"><div class="record-meta">${e(data.students.find(s=>s.id===r.student_id)?.name||'Student')} · ${e(dateTime(r.created_at))}</div><h3>${e(r.title)}</h3><p>${e(r.notes)}</p>${r.tags.map(t=>`<span class="badge">${e(t)}</span>`).join('')}<p class="record-meta">Recorded by ${e(r.author)}</p></article>`).join('')||'<div class="empty">No healthcare notes found.</div>'}</div>`;
 if(page==='prescriptions') body=`<div class="record-grid">${items.map(p=>`<article class="record"><div class="record-meta">RX-${String(p.id).padStart(4,'0')} · ${e(p.created_at)}</div><h3>${e(p.student_name)}</h3><div class="muted">${e(p.doctor_name)} · Appointment #${p.appointment_id}</div><p><strong>Diagnosis:</strong> ${e(p.diagnosis)}</p>${p.items.map(i=>`<div class="prescription-item"><strong>${e(i.medicine_name)}</strong> · ${i.quantity} ${e(i.unit)}<br>${e(i.dosage)}</div>`).join('')}<p>${e(p.instructions)}</p></article>`).join('')||'<div class="empty">No prescriptions yet. Record a consultation to get started.</div>'}</div>`;
 $('#list-content').innerHTML=['records','prescriptions'].includes(page)?body:`<div class="panel">${body}</div>`;
}
function render(){
 const details=meta[page]||meta.dashboard;
 $('#breadcrumb').textContent=details[0];$('#page-title').textContent=details[1];$('#page-description').textContent=details[2];
 $('#page-eyebrow').textContent=page==='dashboard'?'YOUR CAMPUS, AT A GLANCE':'CAMPUS HEALTH WORKSPACE';
 $('#add-button').hidden=!details[3];$('#add-button').textContent='+ '+details[3];
 document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
 if(page==='dashboard') $('#page-content').innerHTML=dashboard();
 else if(page==='analytics') $('#page-content').innerHTML=`<div class="columns">${panel('Visits by month','Non-cancelled appointments · All recorded months',bars(data.analytics.trend,'month','visits'))}${panel('Healthcare themes','Document tags · '+data.analytics.document_store,bars(data.analytics.tags,'tag','count'))}</div><div class="columns">${panel('Department activity','Student coverage and non-cancelled visits',table(['Department','Students','Visits'],data.analytics.departments.map(d=>`<tr><td>${e(d.department)}</td><td>${d.students}</td><td>${d.visits}</td></tr>`)))}${panel('Medicine usage','Units dispensed through prescriptions',bars(data.analytics.medicine_usage,'name','dispensed'))}</div>${panel('Doctor workload','SQL window-function ranking · Non-cancelled visits',table(['Rank','Doctor','Appointments','Completed'],data.analytics.doctors.map(d=>`<tr><td>${d.rank}</td><td>${e(d.name)}</td><td>${d.appointments}</td><td>${d.completed}</td></tr>`)))}`;
 else {$('#page-content').innerHTML=`<div class="toolbar"><input id="search" type="search" aria-label="Search ${e(details[0])}" placeholder="Search ${e(details[0].toLowerCase())}…"></div><div id="list-content"></div>`;renderList();$('#search').addEventListener('input',event=>renderList(event.target.value));}
 applyBars();
}
function field(label,name,type='text',value='',extra=''){return `<label>${e(label)}<input name="${e(name)}" type="${type}" value="${e(value)}" ${extra} required></label>`;}
function select(label,name,options){return `<label>${e(label)}<select name="${name}" required><option value="">Select ${e(label.toLowerCase())}</option>${options.map(([value,text])=>`<option value="${e(value)}">${e(text)}</option>`).join('')}</select></label>`;}
function textarea(label,name){return `<label>${e(label)}<textarea name="${name}" required></textarea></label>`;}
function studentSelect(){return select('Student','student_id',data.students.map(s=>[s.id,`${s.name} · ${s.student_number}`]));}
function openDialog(title,fields,action){$('#dialog-title').textContent=title;$('#form-fields').innerHTML=fields;$('#form-error').textContent='';formAction=action;$('#entity-form button[type="submit"]').hidden=false;$('#form-dialog').showModal();}
function medicineItem(){return `<div class="item-row">${select('Medicine','medicine_id',data.medicines.map(m=>[m.id,`${m.name} · ${m.stock} ${m.unit} available`]))}<div class="field-row">${field('Quantity','quantity','number','1','min="1"')}${field('Dosage / duration','dosage')}</div><button type="button" class="text-button" data-remove-item>Remove medicine</button></div>`;}
function create(entity,identity=null){
 let fields='';
 if(entity==='students') fields=`<div class="field-row">${field('Student number','student_number')}${field('Full name','name')}</div>${field('Email','email','email')}<div class="field-row">${field('Department','department')}${select('Blood group','blood_group',['Unknown','A+','A-','B+','B-','AB+','AB-','O+','O-'].map(v=>[v,v]))}</div><label>Allergies (optional)<textarea name="allergies"></textarea></label>`;
 if(entity==='doctors') fields=field('Full name','name')+field('Specialty','specialty')+field('Email','email','email');
 if(entity==='appointments') fields=studentSelect()+select('Doctor','doctor_id',data.doctors.map(d=>[d.id,`${d.name} · ${d.specialty}`]))+field('Appointment time (30-minute slots)','scheduled_at','datetime-local','','step="1800"')+textarea('Reason for visit','reason');
 if(entity==='medicines') fields=field('Medicine name / batch','name')+`<div class="field-row">${field('Stock','stock','number','0','min="0"')}${field('Unit (tablets, bottles…)','unit')}</div><div class="field-row">${field('Reorder level','reorder_level','number','10','min="0"')}${field('Expiry date','expiry_date','date')}</div>`;
 if(entity==='records') fields=studentSelect()+field('Record title','title')+textarea('Healthcare notes','notes')+'<label>Tags (comma separated)<input name="tags" placeholder="wellness, follow-up"></label>';
 if(entity==='prescriptions') fields='<div class="detail-note">Saving dispenses medicine stock and completes the appointment. Enter the treating doctor’s directions.</div>'+select('Appointment','appointment_id',data.appointments.filter(a=>a.status!=='Cancelled'&&!data.prescriptions.some(p=>p.appointment_id===a.id)).map(a=>[a.id,`#${a.id} · ${a.student_name} · ${dateTime(a.scheduled_at)}`]))+textarea('Diagnosis','diagnosis')+textarea('Instructions','instructions')+`<div id="medicine-items">${medicineItem()}</div><button type="button" class="secondary" id="add-item">+ Add another medicine</button>`;
 openDialog(meta[entity][3],fields,async form=>{if(entity==='records') form.tags=form.tags.split(',').map(t=>t.trim()).filter(Boolean);if(entity==='prescriptions'){form.items=[...document.querySelectorAll('.item-row')].map(row=>Object.fromEntries([...row.querySelectorAll('input,select')].map(input=>[input.name,input.value])));delete form.medicine_id;delete form.quantity;delete form.dosage;}await api(identity?`${entity}/${identity}`:entity,identity?'PUT':'POST',form);});
 if(identity){const record=data[entity].find(r=>r.id===identity);$('#dialog-title').textContent='Edit '+(entity==='students'?'student':'doctor');Object.entries(record).forEach(([key,value])=>{const input=$('#entity-form').elements.namedItem(key);if(input)input.value=value;});}
}
$('#login-form').addEventListener('submit',async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;$('#login-error').textContent='';try{const result=await api('login','POST',Object.fromEntries(new FormData(event.target)));csrf=result.csrf;$('#login-view').hidden=true;$('#workspace').hidden=false;event.target.elements.password.value='';await refresh();}catch(error){$('#login-error').textContent=error.message;}finally{button.disabled=false;}});
$('#logout').addEventListener('click',async()=>{try{await api('logout','POST',{});data={};await showLogin();}catch(error){toast(error.message);}});
$('#add-button').addEventListener('click',()=>create(page==='dashboard'?'appointments':page));
$('#close-dialog').addEventListener('click',()=>$('#form-dialog').close());$('#cancel-dialog').addEventListener('click',()=>$('#form-dialog').close());
$('#entity-form').addEventListener('submit',async event=>{event.preventDefault();const button=event.target.querySelector('button[type="submit"]');button.disabled=true;$('#form-error').textContent='';try{await formAction(Object.fromEntries(new FormData(event.target)));$('#form-dialog').close();toast('Record saved successfully.');await refresh();}catch(error){if($('#form-dialog').open)$('#form-error').textContent=error.message;else toast(error.message);}finally{button.disabled=false;}});
document.addEventListener('click',async event=>{
 const button=event.target.closest('button');if(!button)return;
 try{
 if(button.dataset.page){page=button.dataset.page;render();}
 if(button.dataset.create)create(button.dataset.create);
 if(button.dataset.edit)create(button.dataset.edit,Number(button.dataset.id));
 if(button.id==='add-item')$('#medicine-items').insertAdjacentHTML('beforeend',medicineItem());
 if(button.hasAttribute('data-remove-item')){if(document.querySelectorAll('.item-row').length>1)button.closest('.item-row').remove();else toast('A prescription needs at least one medicine.');}
 if(button.dataset.status){button.disabled=true;await api('appointments/'+button.dataset.id,'PATCH',{status:button.dataset.status});await refresh();toast('Appointment '+button.dataset.status.toLowerCase()+'.');}
 if(button.dataset.restock){const medicine=data.medicines.find(m=>m.id===Number(button.dataset.restock));openDialog('Restock '+medicine.name,`<div class="detail-note">Use this for the same medicine batch and expiry date (${e(medicine.expiry_date)}). Add a separate medicine batch when the expiry date differs.</div>`+field('Quantity to add','quantity','number','1','min="1"'),form=>api(`medicines/${medicine.id}/restock`,'POST',form));}
 if(button.dataset.profile){const student=data.students.find(s=>s.id===Number(button.dataset.profile));const visits=data.appointments.filter(a=>a.student_id===student.id);const notes=data.records.filter(r=>r.student_id===student.id);openDialog(student.name,`<p class="muted">${e(student.student_number)} · ${e(student.department)} · ${e(student.blood_group)}</p><div class="detail-note">Allergies: ${e(student.allergies||'None recorded')}</div><h3>Appointment history</h3>${table(['Visit','Doctor','Status'],visits.map(a=>`<tr><td>${e(dateTime(a.scheduled_at))}</td><td>${e(a.doctor_name)}</td><td>${badge(a.status)}</td></tr>`))}<h3>Healthcare notes</h3>${notes.map(r=>`<div class="record"><strong>${e(r.title)}</strong><p>${e(r.notes)}</p></div>`).join('')||'<p class="muted">No notes recorded.</p>'}`,null);$('#entity-form button[type="submit"]').hidden=true;}
 }catch(error){toast(error.message);button.disabled=false;}
});
(async()=>{try{const current=await api('session');csrf=current.csrf;if(current.username){$('#workspace').hidden=false;await refresh();}else $('#login-view').hidden=false;}catch(error){toast(error.message);}})();
