e => {
 const txt = n => (n?.innerText || n?.textContent || '').trim().replace(/\s+/g,' ');
 const ids = a => (e.getAttribute(a)||'').split(/\s+/).filter(Boolean).map(id=>txt(document.getElementById(id))).join(' ');
 const cloneText = node => { const c=node.cloneNode(true); c.querySelectorAll('input,textarea,select').forEach(x=>x.remove()); return txt(c); };
 let role = e.getAttribute('role');
 if(!role) {
   const type=e.type||'';
   role = e.tagName==='INPUT' ? ({checkbox:'checkbox',radio:'radio',submit:'button',button:'button'}[type]||'textbox') :
   ({BUTTON:'button',A:'link',SELECT:'combobox',TEXTAREA:'textbox',H1:'heading',H2:'heading',H3:'heading',H4:'heading',H5:'heading',H6:'heading',IMG:'img'}[e.tagName]||'text');
 }
 let name = e.getAttribute('aria-label') || ids('aria-labelledby') ||
   Array.from(e.labels||[]).map(cloneText).join(' ') ||
   (['INPUT','TEXTAREA'].includes(e.tagName) ? e.getAttribute('placeholder') || (role==='button' ? e.value : '') : cloneText(e)) ||
   e.getAttribute('alt') || e.getAttribute('title') || '';
 const visible = !!(e.getClientRects().length) && getComputedStyle(e).visibility!=='hidden';
 return {role, name:name.slice(0,200), visible, disabled:e.disabled||e.getAttribute('aria-disabled')==='true',
   tag:e.tagName.toLowerCase(), type:e.type||'', filled:('value' in e ? !!e.value : null), checked:(['checkbox','radio'].includes(e.type) ? e.checked : null), selected:e.tagName==='SELECT' ? Array.from(e.selectedOptions).map(o=>txt(o)) : null, submits:!!e.form && (e.type==='submit' || (e.tagName==='BUTTON' && !e.getAttribute('type'))),
   href:e.tagName==='A' ? e.href : null,
   options:e.tagName==='SELECT' ? Array.from(e.options).map(o=>txt(o)).slice(0,50) : null};
}