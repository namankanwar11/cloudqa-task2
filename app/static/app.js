const $ = id => document.getElementById(id);
let config, current, timer, latest;
const terminal = new Set(["PASS","FAIL","ERROR","BLOCKED","CANCELLED"]);
async function api(path, method="GET", body){
  const response = await fetch(path,{method, headers:{"Content-Type":"application/json","X-Runner-Token":config?.session_token||""},body:body ? JSON.stringify(body):undefined});
  const data = await response.json();
  if(!response.ok) throw new Error(typeof data.detail==="string" ? data.detail : "Invalid request");
  return data;
}
function showError(error){$("error").textContent=error.message;$("error").hidden=false;}
function busy(active){$("run-button").disabled=active;$("demo-button").disabled=active;}
async function start(demo=false){
  $("error").hidden=true;busy(true);clearTimeout(timer);
  try{
    const secrets={};
    if($("email").value) secrets.CUSTOMER_EMAIL=$("email").value;
    if($("password").value) secrets.CUSTOMER_PASSWORD=$("password").value;
    if(demo){$("url").value=location.origin+"/demo";$("instruction").value="Verify the welcome heading is visible.";}
    const request={url:demo?location.origin+"/demo":$("url").value,instruction:demo?"Verify the welcome heading is visible.":$("instruction").value,headless:!$("headed").checked,secrets,mode:demo?"demo":"openai"};
    const result=await api("/api/runs","POST",request);
    $("email").value="";$("password").value="";
    current=result.id;await poll();
  }catch(error){showError(error);busy(false);}
}
function render(report){
  latest=report;$("empty").hidden=true;$("run-output").hidden=false;
  $("status").textContent=report.status;$("status").dataset.status=report.status;
  $("reason").textContent=report.reason;
  $("run-id").textContent=report.mode.toUpperCase()+" · "+report.id.slice(0,10);
  $("elapsed").textContent=report.elapsed_ms ? (report.elapsed_ms/1000).toFixed(1)+"s" : "Running…";
  $("assertions").replaceChildren();
  for(const [id,status] of Object.entries(report.assertions)){
    const line=document.createElement("div"), badge=document.createElement("span");
    badge.className="assert-badge";badge.textContent=status;
    const desc=report.plan?.assertions.find(a=>a.id===id)?.description||id;
    line.append(badge,document.createTextNode(desc));$("assertions").append(line);
  }
  $("timeline").replaceChildren();
  for(const step of report.steps){
    const li=document.createElement("li"), title=document.createElement("strong"), p=document.createElement("p");
    title.textContent=String(step.number).padStart(2,"0")+" · "+step.action.toUpperCase()+" · "+step.status;
    p.textContent=step.detail+" ("+step.elapsed_ms+"ms)";li.append(title,p);
    if(step.screenshot){const a=document.createElement("a"),img=document.createElement("img");a.href=step.screenshot;a.target="_blank";a.rel="noopener";img.src=step.screenshot;img.alt="Masked browser screenshot after step "+step.number;img.loading="lazy";a.append(img);li.append(a);}
    $("timeline").append(li);
  }
  $("approval").hidden=!report.approval;
  if(report.approval) $("approval-text").textContent=report.approval.action.toUpperCase()+" → "+report.approval.control+". "+report.approval.reason;
  $("cancel").hidden=terminal.has(report.status);
  $("download").hidden=!terminal.has(report.status);
  $("download").href="/api/runs/"+report.id+"/report";
  busy(!terminal.has(report.status));
}
async function poll(){
  try{const report=await api("/api/runs/"+current);render(report);if(!terminal.has(report.status))timer=setTimeout(poll,700);}
  catch(error){showError(error);busy(false);}
}
async function decide(approve){
  try{await api("/api/runs/"+current+"/approval","POST",{token:latest.approval.token,approve});$("approval").hidden=true;}
  catch(error){showError(error);}
}
$("test-form").addEventListener("submit",e=>{e.preventDefault();start();});
$("demo-button").addEventListener("click",()=>start(true));
$("approve").addEventListener("click",()=>decide(true));
$("deny").addEventListener("click",()=>decide(false));
$("cancel").addEventListener("click",async()=>{try{await api("/api/runs/"+current+"/cancel","POST");}catch(e){showError(e);}});
api("/api/config").then(c=>{config=c;busy(false);$("model").textContent=c.model;$("config-note").textContent=c.api_key_configured?"OpenAI configured. Click actions pause for your approval.":"OpenAI key not configured. Add OPENAI_API_KEY to .env, then restart. Offline sample requires ALLOW_LOCALHOST=true.";}).catch(showError);