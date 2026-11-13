'use strict';
const data = window.BENCHMARK_REVIEW;
const el = id => document.getElementById(id);
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const labels = {native:'Native A2A',amirk_typed:'Amir typed',mgcrea_typed:'mgcrea typed',mgcrea_raw:'mgcrea raw'};
const conditions = {reference:'Reference',placebo_identity:'Placebo annotation',dropped_fact:'Dropped records',capability_mismatch:'Wrong tool binding',wrong_task:'Wrong task and target',constraint_loss:'Removed constraints',safe_equivalent:'Harmless reorder',recovery:'Dropped records and reread',extraction_loss:'Source extraction loss',compound_records_binding:'Records + binding',compound_identity_constraints:'Identity + constraints',compound_all:'All four faults'};
const parts = {text:'Text',data:'Structured data',file:'File reference',image:'Inline image'};
let view = 'parts';
const json = value => `<pre>${escapeHtml(JSON.stringify(value,null,2))}</pre>`;
const ratio = (n,d) => `${n}/${d}`;
const state = value => `<span class="${value?'good':'fail'}">${value?'Preserved':'Missing or changed'}</span>`;
const table = (heads,rows) => `<div class="table-scroll"><table><thead><tr>${heads.map(h=>`<th scope="col">${escapeHtml(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr><th scope="row">${escapeHtml(row[0])}</th>${row.slice(1).map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;

function overview(){
  if(view==='parts'){
    el('overview').innerHTML=`<h2 id="overview-title">A complete task can lose its required artifact.</h2><p>Each cell shows payload survival / five fresh upstream tasks. Text remains usable through the typed view. Data, file URI and image bytes need the permitted raw read; all 20 eligible same-task recoveries pass.</p>${table(['Required payload',...Object.values(labels)],Object.keys(parts).map(kind=>[parts[kind],...Object.keys(labels).map(route=>{const r=data.partsResult.by_route[route][kind];return `<span class="${r.payload_pass===r.attempts?'good':'fail'}">${ratio(r.payload_pass,r.attempts)}</span>`})]))}<p class="raw-note">Complete artifact fidelity additionally requires media type and, for files/images, filename. mgcrea typed preserves 5/50 required fields; its initial full-artifact score is 0/20. The raw recovery restores 50/50 fields.</p>`;
  }else if(view==='protocol'){
    el('overview').innerHTML=`<h2 id="overview-title">All four routes execute the controlled task contract.</h2><p>Ten known task families under twelve conditions, on four actual routes: 480 episodes. References and authorized rereads pass. Every intended damaging condition fails its original task; no protocol execution errors were recorded.</p>${table(['Condition',...Object.values(labels)],Object.keys(conditions).map(profile=>[conditions[profile],...Object.keys(labels).map(route=>{const r=data.protocolResult.by_route[route][profile];return `<span class="${r.pass===r.attempts?'good':'fail'}">${ratio(r.pass,r.attempts)}</span>`})]))}`;
  }else{
    el('overview').innerHTML=`<h2 id="overview-title">Locate the boundary. Check the smallest repair.</h2><p>160 generated instances of ten known families, twelve conditions, 1,920 episodes. Every changed-field subset is evaluated with the fixed receiver; 6,400 retained interventions verify minimum repair cardinality within four declared groups.</p>${table(['Condition','Task passes','Minimum repair groups','Repair scope'],Object.keys(conditions).map(profile=>{const r=data.diagnosticsResult.by_profile[profile];return [conditions[profile],ratio(r.task_pass,r.attempts),escapeHtml(Object.keys(r.minimum_repair_groups_histogram).join(', ')),profile==='recovery'?'Initial observation, before reread':'Fixed receiver and source snapshot']}))}`;
  }
}
function options(){
  const selected=el('case').value;
  const cases=view==='parts'?Object.keys(parts):data.caseNames.map(x=>x.case_id);
  el('case').innerHTML=cases.map(id=>`<option value="${escapeHtml(id)}">${escapeHtml(view==='parts'?parts[id]:data.caseNames.find(x=>x.case_id===id).family)}</option>`).join('');
  if(cases.includes(selected))el('case').value=selected;
  if(view==='parts'&&!selected)el('case').value='data';
  el('profile').innerHTML=Object.entries(conditions).map(([id,name])=>`<option value="${id}">${name}</option>`).join('');
  if(view==='repairs')el('profile').value='compound_all';
  el('route-control').hidden=view==='repairs';el('profile-control').hidden=view==='parts';
}
function detail(){
  const caseId=el('case').value, route=el('route').value, profile=el('profile').value;
  let row;
  if(view==='parts'){
    row=data.partsCells.find(c=>c.case_id===caseId&&c.route===route);
    const recovered=row.recovery.eligible&&row.recovery.status==='pass';
    el('detail').innerHTML=`<h2>${parts[caseId]} · ${labels[route]}</h2><p>${escapeHtml(row.spec.requirement)}</p><div class="outcome">Payload ${row.required_payload_survived?'preserved':'missing'} · complete artifact ${row.required_representation_survived?'preserved':'incomplete'}${row.recovery.eligible?` · same-task raw recovery ${recovered?'passed':'failed'}`:''}</div><dl class="check-list">${Object.entries(row.field_checks).map(([key,value])=>`<div><dt>${escapeHtml(key)}</dt><dd>${state(value)}</dd></div>`).join('')}</dl><div class="json-grid"><div><h3>Required source artifact</h3>${json(row.spec.expected)}</div><div><h3>Initial public observation</h3>${json(row.observed_artifact_projection)}</div></div>${row.recovery.eligible?`<h3>Same-task raw recovery</h3>${json(row.recovery.observed_artifact)}<p class="raw-note">One GetTask read, using the original public task ID and context. No new task or SendMessage.</p>`:''}<details><summary>Inspect the public final read</summary>${json(row.final)}</details>`;
    el('selection-note').textContent='Showing repetition 0 of five. The complete allocation preserves every attempt.';
  }else if(view==='protocol'){
    row=data.protocolCells.find(c=>c.case_id===caseId&&c.route===route&&c.profile===profile);
    el('detail').innerHTML=`<h2>${labels[route]} · ${conditions[profile]}</h2><div class="outcome">Original task ${row.task_completion==='pass'?'passed':'failed'} · actual authoritative final read retained</div><dl class="check-list"><div><dt>Reference read probe</dt><dd>${state(row.capability_probes[0].decoded.usable)}</dd></div><div><dt>Receiver read probe</dt><dd>${state(row.capability_probes[1].decoded.usable)}</dd></div><div><dt>Recovery</dt><dd>${escapeHtml(row.recovery.status==='not_applicable'?'N/A':row.recovery.status)}</dd></div></dl><div class="json-grid"><div><h3>Initial converted observation</h3>${json(row.observation.received)}</div><div><h3>Final receiver result</h3>${json(row.service_result)}</div></div><details><summary>Inspect the public task receipt</summary>${json(row.receipt)}</details>`;
    el('selection-note').textContent='Known controlled task, real protocol execution. Read probes are separate from the episode.';
  }else{
    row=data.diagnosticCells.find(c=>c.case_id===caseId&&c.profile===profile);
    const cert=row.diagnosis.repair_certificate;
    const stageRows=Object.entries(row.diagnosis.boundaries).filter(([key])=>key!=='raw_conversion').map(([key,value])=>[key,ratio(value.kept,value.eligible_leaves),String(value.changed),String(value.missing)]);
    el('detail').innerHTML=`<h2>${conditions[profile]} · checked repair</h2><div class="outcome">${cert.trial_count} interventions retained · minimum ${cert.minimum_repair_group_count} repair groups</div>${table(['Boundary','Leaves kept','Changed','Missing'],stageRows)}<h3>Inclusion-minimal repair sets</h3>${json(cert.minimal_repair_sets)}<p class="raw-note">Exhaustive only within records, task identity, constraints and tool binding. Repair interventions use source fields and the fixed receiver. Their cost is separate from task overhead.</p><details open><summary>Intervention outcomes</summary>${table(['Restored groups','Original task'],cert.trials.map(t=>[t.restore.join(' + ')||'None',`<span class="${t.assessment.task_completion==='pass'?'good':'fail'}">${t.assessment.task_completion}</span>`]))}</details>`;
    el('selection-note').textContent='Showing generated variant 0. Sixteen transformations per family are development instances.';
  }
  el('raw-link').href='../../'+row.raw_path;
}
function render(){overview();options();detail()}
for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>{view=button.dataset.view;for(const b of document.querySelectorAll('[data-view]'))b.setAttribute('aria-pressed',String(b===button));render()});
for(const id of ['case','route','profile'])el(id).addEventListener('change',detail);
el('print').addEventListener('click',()=>window.print());
if(data){render()}else{el('overview').innerHTML='<h2>Review data unavailable</h2><p>Keep data.js beside index.html, then reload. The Markdown report remains available.</p>';el('evidence').hidden=true;document.querySelectorAll('[data-view]').forEach(b=>b.disabled=true)}
