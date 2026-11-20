'use strict';
const $ = (sel, root=document) => root.querySelector(sel);
const app = { user: null, section: 'catalog', books: [], students: [] };
const escapeHtml = (v) => String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmt = (d) => d ? new Date(d.length===10?`${d}T12:00:00`:d).toLocaleDateString('es-AR',{day:'2-digit',month:'2-digit',year:'numeric'}) : '—';
const maybeNum = (n) => Number(n)||0;
const badge = (status, due) => {
  if (status==='ready') return '<span class="pill">Lista para retirar</span>';
  if (status==='waiting') return '<span class="pill waiting">En espera</span>';
  if (status==='fulfilled') return '<span class="pill neutral">Retirada</span>';
  if (status==='cancelled') return '<span class="pill neutral">Cancelada</span>';
  if (status==='expired') return '<span class="pill danger">Vencida</span>';
  if (status==='returned') return '<span class="pill neutral">Devuelto</span>';
  if (due && due < new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Argentina/Buenos_Aires'}).format(new Date())) return '<span class="pill danger">Vencido</span>';
  return '<span class="pill">Activo</span>';
};

async function api(route, options={}) {
  const opts={credentials:'same-origin',...options};
  if (opts.body && typeof opts.body !== 'string') opts.body=JSON.stringify(opts.body);
  if (opts.body) opts.headers={'Content-Type':'application/json',...(opts.headers||{})};
  let res;
  try {res=await fetch(route, opts);} catch {throw new Error('No se pudo conectar con el servidor');}
  let data; try{data=await res.json();}catch{throw new Error('Respuesta inesperada del servidor');}
  if (!res.ok) {
    if (res.status===401 && route!=='/api/auth/login') showLogin();
    throw new Error(data.error||`Error ${res.status}`);
  }
  return data;
}

let toastTimer;
function toast(message, error=false){
  const el=$('#toast'); el.textContent=message; el.className=`toast${error?' error':''}`;
  clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.classList.add('hidden'),4000);
}
function showLogin(){app.user=null; $('#app-view').classList.add('hidden');$('#login-view').classList.remove('hidden');}
function showApp(user){
  app.user=user; app.section=user.role==='admin'?'dashboard':'catalog';
  $('#login-view').classList.add('hidden');$('#app-view').classList.remove('hidden');
  $('#sidebar-name').textContent=user.name;
  $('#sidebar-role').textContent=user.role==='admin'?'Personal de biblioteca':'Alumno';
  $('#today-label').textContent=new Date().toLocaleDateString('es-AR',{day:'2-digit',month:'short',year:'numeric'});
  renderNav(); navigate(app.section);
}
function renderNav(){
  const admin=app.user.role==='admin';
  const items=admin?[['dashboard','◫','Panel de control'],['catalog','▤','Catálogo'],['loans','↗','Préstamos'],['reservations','◷','Reservas'],['students','♙','Alumnos']]:[['catalog','▤','Catálogo'],['my','◫','Mis movimientos']];
  $('#nav').innerHTML=items.map(([id,ico,label])=>`<button class="navlink${app.section===id?' active':''}" data-go="${id}"><span class="navicon">${ico}</span>${label}</button>`).join('');
}
async function navigate(section){
  app.section=section;renderNav();
  const title={catalog:'Catálogo',my:'Mis movimientos',dashboard:'Panel de control',loans:'Préstamos',reservations:'Reservas',students:'Alumnos'}[section]||'Inicio';
  $('#crumb-title').textContent=title.toUpperCase();$('#page').innerHTML='<div class="empty">Cargando información…</div>';
  try {
    if (section==='catalog') await catalog();
    else if (section==='my') await myPage();
    else if (section==='dashboard') await dashboard();
    else if (section==='loans') await loansPage();
    else if (section==='reservations') await reservationsPage();
    else if (section==='students') await studentsPage();
  }catch(ex){toast(ex.message,true);$('#page').innerHTML=`<div class="empty">${escapeHtml(ex.message)}</div>`;}
}
const pageHead=(tag,title,subtitle,actions='')=>`<div class="page-head"><div><span class="tagline">${tag}</span><h1>${title}</h1><p class="muted">${subtitle}</p></div>${actions}</div>`;

async function catalog(){
  const admin=app.user.role==='admin';
  const data=await api('/api/books');app.books=data.books;
  let reserves=new Set();
  if (!admin){const mine=await api('/api/my');reserves=new Set(mine.reservations.filter(r=>['ready','waiting'].includes(r.status)).map(r=>r.book_id));}
  $('#page').innerHTML=pageHead('EXPLORÁ NUESTRA COLECCIÓN','Catálogo de libros','Encontrá libros por título, autor o categoría.',admin?'<button class="btn primary" id="add-book">+ Agregar libro</button>':'')+
     `<div class="toolbar"><input id="book-search" class="search-input" placeholder="⌕  Buscar título, autor o categoría…" aria-label="Buscar libros" /><span class="count" id="book-count"></span></div><div id="book-list" class="book-grid"></div>`;
  drawBooks(data.books,reserves);
  $('#book-search').addEventListener('input',()=>drawBooks(app.books.filter(b=>[b.title,b.author,b.category].some(x=>x.toLocaleLowerCase().includes($('#book-search').value.toLocaleLowerCase()))),reserves));
  if (admin) $('#add-book').addEventListener('click',()=>bookModal());
}
function drawBooks(books,reserves){
  $('#book-count').textContent=`${books.length} título${books.length===1?'':'s'}`;
  $('#book-list').innerHTML=books.length?books.map(b=>`<article class="book-card"><div class="book-top"><span class="book-chip">${escapeHtml(b.category)}</span><span class="muted">#${b.id}</span></div><div class="book-glyph" aria-hidden="true">▥</div><h3>${escapeHtml(b.title)}</h3><p>${escapeHtml(b.author)}</p><span class="book-note">${b.copies} ejemplar${b.copies===1?'':'es'} · ${b.waiting} en espera</span><div class="book-bottom"><span class="availability${b.available?'':' none'}">● ${b.available?`${b.available} disponible${b.available===1?'':'s'}`:'Sin ejemplares libres'}</span>${app.user.role==='admin'?`<button class="btn minor" data-edit-book="${b.id}">Editar</button>`:`<button class="btn minor ${reserves.has(b.id)?'ghost':''}" ${reserves.has(b.id)?'disabled':''} data-reserve="${b.id}">${reserves.has(b.id)?'Ya reservado':'Reservar →'}</button>`}</div></article>`).join(''):'<div class="empty">No se encontraron libros.</div>';
  document.querySelectorAll('[data-edit-book]').forEach(el=>el.addEventListener('click',()=>bookModal(app.books.find(b=>b.id===+el.dataset.editBook))));
  document.querySelectorAll('[data-reserve]').forEach(el=>el.addEventListener('click',async()=>{
    el.disabled=true;
    try{const result=await api('/api/reservations',{method:'POST',body:{book_id:+el.dataset.reserve}});
      toast(result.reservation.status==='ready'?'Reserva confirmada. Tenés 48 horas para retirar':'Te agregamos a la lista de espera');await catalog();
    }catch(ex){el.disabled=false;toast(ex.message,true);}
  }));
}
async function myPage(){
  const data=await api('/api/my');
  const active=data.loans.filter(l=>!l.returned_at);
  const current=data.reservations.filter(r=>['ready','waiting'].includes(r.status));
  $('#page').innerHTML=pageHead('TU ACTIVIDAD','Mis movimientos','Consultá tus préstamos, fechas de devolución y reservas.')+
    `<div class="stats"><div class="stat"><small>PRÉSTAMOS ACTIVOS</small><div class="number">${active.length}<span class="mini-icon">↗</span></div></div><div class="stat"><small>RESERVAS ACTIVAS</small><div class="number">${current.length}<span class="mini-icon">◷</span></div></div><div class="stat"><small>CUPO DISPONIBLE</small><div class="number">${Math.max(0,3-active.length)}<span class="mini-icon">▤</span></div></div><div class="stat"><small>PRÉSTAMOS VENCIDOS</small><div class="number">${active.filter(l=>l.due_on<data.today).length}<span class="mini-icon">!</span></div></div></div>`+
   `<section class="panel"><h2>Mis préstamos</h2><p class="panel-sub">Cada préstamo dura 14 días; podés renovarlo una vez por 7 días si nadie espera.</p><div class="table-scroll"><table><thead><tr><th>LIBRO</th><th>VENCIMIENTO</th><th>ESTADO</th><th>ACCIÓN</th></tr></thead><tbody>${data.loans.map(l=>`<tr><td><strong>${escapeHtml(l.title)}</strong></td><td>${fmt(l.due_on)}</td><td>${badge(l.returned_at?'returned':'active',l.returned_at?null:l.due_on)}</td><td>${!l.returned_at?`<button class="btn minor" data-renew="${l.id}" ${l.renewal_count?'disabled':''}>${l.renewal_count?'Ya renovado':'Renovar +7 días'}</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Todavía no tenés préstamos.</td></tr>'}</tbody></table></div></section>`+
   `<section class="panel"><h2>Mis reservas</h2><p class="panel-sub">Si tu reserva está lista, tenés 48 horas para retirar el libro en la biblioteca.</p><div class="table-scroll"><table><thead><tr><th>LIBRO</th><th>ESTADO</th><th>FECHA LÍMITE</th><th>ACCIÓN</th></tr></thead><tbody>${data.reservations.map(r=>`<tr><td><strong>${escapeHtml(r.title)}</strong></td><td>${badge(r.status)}</td><td>${fmt(r.expires_at)}</td><td>${['ready','waiting'].includes(r.status)?`<button class="btn minor ghost" data-cancel="${r.id}">Cancelar</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">No tenés reservas registradas.</td></tr>'}</tbody></table></div></section>`;
  document.querySelectorAll('[data-renew]').forEach(el=>el.addEventListener('click',()=>perform(`/api/loans/${el.dataset.renew}/renew`,'POST','Préstamo renovado',myPage)));
  document.querySelectorAll('[data-cancel]').forEach(el=>el.addEventListener('click',()=>perform(`/api/reservations/${el.dataset.cancel}`,'DELETE','Reserva cancelada',myPage)));
}
async function dashboard(){
  const [stats,logs,reservations]=await Promise.all([api('/api/admin/dashboard'),api('/api/admin/loans'),api('/api/admin/reservations')]);
  const active=logs.loans.filter(x=>!x.returned_at).slice(0,6);
  $('#page').innerHTML=pageHead('VISTA GENERAL','Panel de control','Todo lo que necesitás saber sobre la biblioteca hoy.')+
   `<div class="hero-band"><div><span class="tagline">GESTIÓN DE BIBLIOTECA</span><h2>Una biblioteca mejor organizada.</h2><p>Administrá ejemplares, registrá préstamos y respetá automáticamente las listas de espera.</p><button class="btn primary" data-go="loans">Registrar préstamo ↗</button></div><div class="hero-icon" aria-hidden="true">▥</div></div>`+
   `<div class="stats"><div class="stat"><small>TÍTULOS EN CATÁLOGO</small><span class="mini-icon">▤</span><div class="number">${stats.titles}</div></div><div class="stat"><small>ALUMNOS REGISTRADOS</small><span class="mini-icon">♙</span><div class="number">${stats.students}</div></div><div class="stat"><small>PRÉSTAMOS ACTIVOS</small><span class="mini-icon">↗</span><div class="number">${stats.active_loans}</div></div><div class="stat"><small>PRÉSTAMOS VENCIDOS</small><span class="mini-icon">◷</span><div class="number">${stats.overdue}</div></div></div>`+
   `<div class="split"><section class="panel"><h2>Últimos préstamos activos</h2><p class="panel-sub">Préstamos todavía sin devolver.</p><div class="table-scroll"><table><thead><tr><th>LIBRO</th><th>ALUMNO</th><th>DEVOLUCIÓN</th></tr></thead><tbody>${active.map(l=>`<tr><td>${escapeHtml(l.title)}</td><td>${escapeHtml(l.student)}</td><td>${fmt(l.due_on)}</td></tr>`).join('')||'<tr><td colspan="3" class="empty">Todavía no hay préstamos.</td></tr>'}</tbody></table></div></section><section class="panel"><h2>Estado de reservas</h2><p class="panel-sub">${stats.ready} listas para retirar · ${stats.waiting} en espera</p><div class="table-scroll"><table><thead><tr><th>LIBRO</th><th>ALUMNO</th><th>ESTADO</th></tr></thead><tbody>${reservations.reservations.slice(0,6).map(r=>`<tr><td>${escapeHtml(r.title)}</td><td>${escapeHtml(r.student)}</td><td>${badge(r.status)}</td></tr>`).join('')||'<tr><td colspan="3" class="empty">Sin reservas activas.</td></tr>'}</tbody></table></div></section></div>`;
  $('#page').querySelector('[data-go]').addEventListener('click',()=>navigate('loans'));
}
async function loansPage(){
  const [result,books,students]=await Promise.all([api('/api/admin/loans'),api('/api/books'),api('/api/admin/students')]);
  app.books=books.books;app.students=students.students;
  $('#page').innerHTML=pageHead('ADMINISTRACIÓN','Gestión de préstamos','Registrá retiros y devoluciones; las reglas de disponibilidad se validan en el servidor.',
     '<button class="btn primary" id="checkout-new">+ Registrar préstamo</button>')+
   `<section class="panel"><h2>Historial de préstamos</h2><p class="panel-sub">Incluye activos, vencidos y devueltos.</p><div class="table-scroll"><table><thead><tr><th>LIBRO</th><th>ALUMNO</th><th>RETIRADO</th><th>VENCE</th><th>ESTADO</th><th>ACCIÓN</th></tr></thead><tbody>${result.loans.map(l=>`<tr><td><strong>${escapeHtml(l.title)}</strong></td><td>${escapeHtml(l.student)}<br><span class="muted">${escapeHtml(l.email)}</span></td><td>${fmt(l.borrowed_at)}</td><td>${fmt(l.due_on)}</td><td>${badge(l.returned_at?'returned':'active',l.returned_at?null:l.due_on)}</td><td>${!l.returned_at?`<button class="btn minor" data-return="${l.id}">Marcar devolución</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">No hay préstamos registrados.</td></tr>'}</tbody></table></div></section>`;
  $('#checkout-new').addEventListener('click',()=>checkoutModal());
  document.querySelectorAll('[data-return]').forEach(el=>el.addEventListener('click',()=>perform(`/api/admin/loans/${el.dataset.return}/return`,'POST','Devolución registrada',loansPage)));
}
async function reservationsPage(){
  const data=await api('/api/admin/reservations');
  $('#page').innerHTML=pageHead('LISTA DE ESPERA','Reservas de libros','Las reservas se asignan por orden de llegada. El retiro se mantiene durante 48 horas.')+
   `<section class="panel"><h2>Reservas activas</h2><p class="panel-sub">Listas para retirar y pendientes por disponibilidad.</p><div class="table-scroll"><table><thead><tr><th>LIBRO</th><th>ALUMNO</th><th>ESTADO</th><th>SOLICITADA</th><th>RETIRAR HASTA</th><th>ACCIÓN</th></tr></thead><tbody>${data.reservations.map(r=>`<tr><td><strong>${escapeHtml(r.title)}</strong></td><td>${escapeHtml(r.student)}<br><span class="muted">${escapeHtml(r.email)}</span></td><td>${badge(r.status)}</td><td>${fmt(r.created_at)}</td><td>${fmt(r.expires_at)}</td><td><button class="btn minor ghost" data-cancel="${r.id}">Cancelar</button></td></tr>`).join('')||'<tr><td colspan="6" class="empty">No hay reservas activas.</td></tr>'}</tbody></table></div></section>`;
  document.querySelectorAll('[data-cancel]').forEach(el=>el.addEventListener('click',()=>perform(`/api/reservations/${el.dataset.cancel}`,'DELETE','Reserva cancelada',reservationsPage)));
}
async function studentsPage(){
  const data=await api('/api/admin/students');
  app.students=data.students;
  $('#page').innerHTML=pageHead('COMUNIDAD','Alumnos registrados','Gestioná el acceso de estudiantes a la biblioteca.',
    '<button class="btn primary" id="add-student">+ Nuevo alumno</button>')+
    `<section class="panel"><h2>Directorio de alumnos</h2><p class="panel-sub">${data.students.length} alumnos.</p><div class="table-scroll"><table><thead><tr><th>ID</th><th>NOMBRE</th><th>CORREO</th><th>ESTADO</th></tr></thead><tbody>${data.students.map(s=>`<tr><td>#${s.id}</td><td><strong>${escapeHtml(s.name)}</strong></td><td>${escapeHtml(s.email)}</td><td>${s.active?'<span class="pill">Activo</span>':'<span class="pill neutral">Inactivo</span>'}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">No hay alumnos.</td></tr>'}</tbody></table></div></section>`;
  $('#add-student').addEventListener('click',()=>studentModal());
}

function modal(title,description,fields,submitLabel,onSubmit){
  const overlay=document.createElement('div');overlay.className='modal-overlay';
  overlay.innerHTML=`<section class="modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}"><h2>${escapeHtml(title)}</h2><p class="muted">${escapeHtml(description)}</p><form id="modal-form">${fields}<div class="modal-footer"><button class="btn" type="button" id="close-modal">Cancelar</button><button class="btn primary" type="submit">${escapeHtml(submitLabel)}</button></div></form></section>`;
  document.body.appendChild(overlay);
  const close=()=>overlay.remove();
  $('#close-modal',overlay).addEventListener('click',close);
  overlay.addEventListener('click',e=>{if(e.target===overlay)close();});
  $('#modal-form',overlay).addEventListener('submit',async e=>{
    e.preventDefault();const submit=$('button[type="submit"]',overlay);submit.disabled=true;
    const f=Object.fromEntries(new FormData(e.target).entries());
    try{await onSubmit(f);close();}catch(ex){toast(ex.message,true);}finally{if(submit.isConnected)submit.disabled=false;}
  });
  $('input,select',overlay)?.focus();
}
function field(name,label,type='text',value='',required=true){return `<label for="f-${name}">${label}</label><input id="f-${name}" class="form-input" name="${name}" type="${type}" value="${escapeHtml(value??'')}" ${required?'required':''} ${type==='number'?'min="1" max="1000"':''} />`;}
function bookModal(book){
  modal(book?'Editar libro':'Agregar libro','Completá los datos del ejemplar para el catálogo.',
    field('title','Título','text',book?.title)+field('author','Autor','text',book?.author)+field('category','Categoría','text',book?.category)+field('isbn','ISBN (opcional)','text',book?.isbn||'',false)+field('copies','Cantidad de ejemplares','number',book?.copies||1),
    book?'Guardar cambios':'Agregar',async f=>{
      await api(book?`/api/admin/books/${book.id}`:'/api/admin/books',{method:book?'PATCH':'POST',body:f});toast(book?'Libro actualizado':'Libro agregado');await catalog();
    });
}
function studentModal(){
  modal('Nuevo alumno','Creá una cuenta para que el alumno consulte reservas y préstamos.',
    field('name','Nombre completo')+field('email','Correo electrónico','email')+field('password','Contraseña inicial (mínimo 8 caracteres)','password'),
    'Crear alumno',async f=>{await api('/api/admin/students',{method:'POST',body:f});toast('Alumno creado');await studentsPage();});
}
function checkoutModal(){
  const bookOptions=app.books.map(b=>`<option value="${b.id}">${escapeHtml(b.title)} (${b.available} libres)</option>`).join('');
  const studentOptions=app.students.map(s=>`<option value="${s.id}">${escapeHtml(s.name)} — ${escapeHtml(s.email)}</option>`).join('');
  modal('Registrar préstamo','El servidor verifica cupo, vencimientos, reservas y disponibilidad.',
    `<label for="loan-student">Alumno</label><select id="loan-student" class="select-input" name="user_id" required>${studentOptions}</select><label for="loan-book">Libro</label><select id="loan-book" class="select-input" name="book_id" required>${bookOptions}</select>`,
    'Confirmar retiro',async f=>{await api('/api/admin/checkout',{method:'POST',body:f});toast('Préstamo creado con vencimiento a 14 días');await loansPage();});
}
async function perform(url,method,message,refresh){
  try{await api(url,{method});toast(message);await refresh();}catch(ex){toast(ex.message,true);}
}
$('#login-form').addEventListener('submit',async e=>{
  e.preventDefault();$('#login-error').textContent='';
  const button=$('#login-form button[type="submit"]');button.disabled=true;
  try{const data=await api('/api/auth/login',{method:'POST',body:{email:$('#email').value,password:$('#password').value}});$('#password').value='';showApp(data.user);}
  catch(ex){$('#login-error').textContent=ex.message;}
  finally{button.disabled=false;}
});
$('#nav').addEventListener('click',e=>{const target=e.target.closest('[data-go]');if(target) navigate(target.dataset.go);});
$('#logout').addEventListener('click',async()=>{try{await api('/api/auth/logout',{method:'POST'});}catch{}showLogin();toast('Sesión cerrada');});
api('/api/me').then(d=>showApp(d.user)).catch(()=>showLogin());
