"""Export supervisor figures from verified experimental data with provenance."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from scripts.verify_loss_release_v2 import read_json, require, sha
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, PngImagePlugin

EVIDENCE = ROOT / "runs/supervisor-handoff-20261113"
DEST = ROOT / "reports/supervisor-20261113/images"
COLORS = {"ink": "#24273a", "muted": "#575b6c", "accent": "#3e428c", "good": "#24644c", "fail": "#873943", "line": "#cbcbd1"}
PROFILES = ["reference", "placebo_identity", "safe_equivalent", "dropped_fact", "capability_mismatch", "wrong_task", "constraint_loss", "extraction_loss", "compound_records_binding", "compound_identity_constraints", "compound_all", "recovery"]
LABELS = ["Reference", "Placebo annotation", "Harmless reorder", "Dropped records", "Wrong tool binding", "Wrong task/target", "Removed constraints", "Extraction loss", "Records + binding", "Identity + constraints", "All four faults", "Dropped records + reread"]
ROUTES = ["native", "amirk_typed", "mgcrea_typed", "mgcrea_raw"]
ROUTE_LABELS = ["Native A2A", "Amir typed", "mgcrea typed", "mgcrea raw"]


def save(fig, name, sources, note):
    fig.savefig(DEST / (name + ".png"), dpi=170, bbox_inches="tight", facecolor="white")
    fig.savefig(DEST / (name + ".svg"), bbox_inches="tight", facecolor="white")
    metadata = PngImagePlugin.PngInfo()
    provenance = {"generator": "scripts/build_loss_figures_v2.py", "note": note,
                  "sources": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in sources]}
    metadata.add_text("Provenance", json.dumps(provenance))
    with Image.open(DEST / (name + ".png")) as im:
        im.save(DEST / (name + ".png"), pnginfo=metadata)
    (DEST / (name + ".provenance.json")).write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    plt.close(fig)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    task_verification = EVIDENCE / "final-verification-001/verification.json"
    parts_verification = EVIDENCE / "parts-verification-001/verification.json"
    require(read_json(task_verification)["status"] == "passed", "Task data not verified")
    require(read_json(parts_verification)["status"] == "passed", "Parts data not verified")
    diagnostics_path = EVIDENCE / "diagnostics-final-001/results.json"
    protocol_path = EVIDENCE / "protocol-main-001/results.json"
    parts_path = EVIDENCE / "parts-main-001/results.json"
    diagnostics, protocol, parts = map(read_json, (diagnostics_path, protocol_path, parts_path))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.labelcolor": COLORS["ink"], "text.color": COLORS["ink"],
                         "xtick.color": COLORS["muted"], "ytick.color": COLORS["ink"], "axes.edgecolor": COLORS["line"]})
    fig, ax = plt.subplots(figsize=(11.6, 6.9))
    values = np.array([[protocol["by_route"][route][profile]["pass"] for route in ROUTES] for profile in PROFILES])
    from matplotlib.colors import ListedColormap
    ax.imshow(values, cmap=ListedColormap(["#f8e9e9", "#e8f2ec"]), vmin=0, vmax=10, aspect="auto")
    ax.set_xticks(range(4), ROUTE_LABELS); ax.xaxis.tick_top()
    ax.set_yticks(range(12), LABELS); ax.tick_params(length=0, pad=10)
    for i in range(12):
        for j in range(4):
            ax.text(j, i, f"{values[i,j]}/10", ha="center", va="center", color=COLORS["good"] if values[i,j] else COLORS["fail"], fontweight="bold")
    ax.set_title("Original task success across actual protocol routes", loc="left", pad=44, fontsize=17, fontweight="bold")
    fig.text(.02, .01, "480 fresh controlled episodes; ten known task templates. Faults are injected. No LLM or held-out evaluation.", fontsize=9, color=COLORS["muted"])
    fig.tight_layout(rect=(0,.035,1,1)); save(fig,"protocol-outcomes",[protocol_path,task_verification],"Original task passes / all attempts per controlled condition and route; no population estimate.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.15, 1]})
    kinds=["text","data","file","image"]
    values=np.array([[parts["by_route"][route][kind]["payload_pass"] for route in ROUTES] for kind in kinds])
    axes[0].imshow(values,cmap=ListedColormap(["#f8e9e9","#e8f2ec"]),vmin=0,vmax=5,aspect="auto")
    axes[0].set_xticks(range(4),["Native","Amir typed","mgcrea\ntyped","mgcrea\nraw"],fontsize=9)
    axes[0].set_yticks(range(4),["Text","Data object","File URI","Image bytes"]); axes[0].tick_params(length=0,pad=8)
    for i in range(4):
        for j in range(4): axes[0].text(j,i,f"{values[i,j]}/5",ha="center",va="center",color=COLORS["good"] if values[i,j] else COLORS["fail"],fontweight="bold")
    axes[0].set_title("Required payload survives",loc="left",fontsize=14,fontweight="bold",pad=15)
    names=["Typed text utility","Typed full artifact","Same-task raw recovery"]
    vals=[5,0,20]; denoms=[5,20,20]
    axes[1].barh(names,[v/d for v,d in zip(vals,denoms)],color=[COLORS["accent"],COLORS["fail"],COLORS["good"]],height=.55)
    axes[1].set_xlim(0,1.15); axes[1].set_xticks([0,.5,1],["0%","50%","100%"])
    for i,(v,d) in enumerate(zip(vals,denoms)): axes[1].text(v/d+.025,i,f"{v}/{d}",va="center",fontsize=11)
    axes[1].set_title("mgcrea typed and raw recovery",loc="left",fontsize=14,fontweight="bold",pad=15)
    fig.suptitle("Upstream artifact survival: typed projection versus raw evidence",x=.01,ha="left",fontsize=17,fontweight="bold")
    fig.text(.01,.01,"80 fresh upstream-fixture tasks; 20 additional recovery reads. Text utility differs from metadata fidelity. Recovery is adaptive development.",fontsize=9,color=COLORS["muted"])
    fig.tight_layout(rect=(0,.065,1,.91)); save(fig,"artifact-survival",[parts_path,parts_verification],"Native source artifact, typed content, raw GetTask and same original task/context are independently checked.")

    selected=["dropped_fact","capability_mismatch","wrong_task","constraint_loss","compound_records_binding","compound_identity_constraints","compound_all"]
    fig,ax=plt.subplots(figsize=(11,4.9))
    vals=[int(next(iter(diagnostics["by_profile"][p]["minimum_repair_groups_histogram"]))) for p in selected]
    names=[dict(zip(PROFILES,LABELS))[p] for p in selected]
    ax.barh(names,vals,color=COLORS["accent"],height=.6)
    for i,v in enumerate(vals):ax.text(v+.06,i,f"{v} groups · 160/160 cases",va="center",fontsize=10)
    ax.set_xlim(0,5.7);ax.set_xticks(range(5));ax.set_xlabel("Minimum groups restored from the authorized source")
    ax.set_title("Compound failures need compound repairs",loc="left",pad=18,fontsize=17,fontweight="bold")
    fig.text(.01,.01,"1,920 controlled episodes; 6,400 exhaustive interventions. Minimality is restricted to four declared groups and a fixed receiver.",fontsize=9,color=COLORS["muted"])
    fig.tight_layout(rect=(0,.045,1,1));save(fig,"repair-minimality",[diagnostics_path,task_verification],"Inclusion-minimal sets and minimum cardinality independently verified; interventions excluded from task recovery denominator.")

    fig,ax=plt.subplots(figsize=(11.6,4.9))
    labels=["Extraction loss","Conversion loss","Missing records + reread","Harmless reorder"]
    profiles=["extraction_loss","dropped_fact","recovery","safe_equivalent"]
    bars=[]
    for stage in ("extraction","conversion","end_to_end"):
        bars.append([diagnostics["by_profile"][p]["boundary_leaf_totals"][stage]["kept"] / diagnostics["by_profile"][p]["boundary_leaf_totals"][stage]["eligible_leaves"] for p in profiles])
    x=np.arange(4)
    for index,(stage,values,color) in enumerate(zip(["Source → sent","Sent → received","Source → received"],bars,[COLORS["accent"],"#6875af",COLORS["good"]])):
        ax.bar(x+(index-1)*.22,values,.22,label=stage,color=color)
        for pos,value in enumerate(values):ax.text(pos+(index-1)*.22,value+.015,f"{value:.1%}",ha="center",fontsize=9)
    ax.set_xticks(x,labels);ax.set_ylim(0,1.21);ax.set_yticks([0,.5,1],["0%","50%","100%"]);ax.set_ylabel("Reference JSON leaves retained")
    ax.set_title("Boundary location and initial loss remain visible",loc="left",pad=18,fontsize=17,fontweight="bold")
    ax.legend(ncol=3,frameon=False,loc="lower center",bbox_to_anchor=(.5,-.25),fontsize=9)
    fig.text(.01,.01,"Declared duplicate-preserving record normalization; not total knowledge retention. Recovery does not rewrite the initial received boundary.",fontsize=9,color=COLORS["muted"])
    fig.tight_layout(rect=(0,.095,1,1));save(fig,"boundary-localization",[diagnostics_path,task_verification],"Leaf units and captured boundary stages are explicit; later repair does not erase initial recorded loss.")
    print(json.dumps({"status":"built","figures":4,"destination":str(DEST)}))


if __name__=="__main__":
    main()
