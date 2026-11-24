function openModal(id){const m=document.getElementById(id);if(m)m.classList.add('open')}
function closeModal(id){const m=document.getElementById(id);if(m)m.classList.remove('open')}
document.querySelectorAll('.modal').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('open')}));
document.querySelectorAll('[data-table-search]').forEach(input=>input.addEventListener('input',()=>{const table=document.getElementById(input.dataset.tableSearch);if(!table)return;const q=input.value.toLowerCase();table.querySelectorAll('tbody tr').forEach(row=>row.style.display=row.innerText.toLowerCase().includes(q)?'':'none')}));
function addOrderRow(){const root=document.getElementById('order-lines');const original=root.querySelector('.order-line');if(!original)return;const clone=original.cloneNode(true);clone.querySelectorAll('input').forEach(i=>i.value='');root.appendChild(clone)}
function removeOrderRow(btn){const root=document.getElementById('order-lines');if(root.querySelectorAll('.order-line').length>1)btn.closest('.order-line').remove()}
setTimeout(()=>document.querySelectorAll('.flash').forEach(f=>{f.style.transition='opacity .4s';f.style.opacity='0';setTimeout(()=>f.remove(),450)}),6500);
