"""Canonical release and pytest-input fingerprinting for EGCM evidence."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Mapping
SCHEMA_VERSION="2.0"; ALGORITHM="sha256"
EXCLUDED_DIRS={".git",".pytest_cache","__pycache__","outputs","output","release_validation","validation_review_corrected","calibration_work","greenland_check"}
EXCLUDED_SUFFIXES={".pyc",".pyo",".tmp",".bak",".tolbak",".stage0",".pid",".exit",".log"}
EXECUTABLE_SUFFIXES={".py",".pyw",".sh",".bat",".ps1",".toml",".in",".lock",".yml",".yaml"}; RELEASE_SUFFIXES=EXECUTABLE_SUFFIXES|{".md"}
ROOT_RUNTIME_INPUTS={".gitignore","calibration_targets.json","climate_model_settings_increased_sv_from_melt.json","dependency_integrity.lock.json","development_regression_benchmarks.json","external_posthoc_sanity_benchmarks.json","held_out_amoc_benchmarks.json"}
def sha256_file(path:Path)->str:
 d=hashlib.sha256();
 with path.open("rb") as h:
  for chunk in iter(lambda:h.read(1024*1024),b""): d.update(chunk)
 return d.hexdigest()
def _included(root:Path,path:Path,profile:str)->bool:
 r=path.relative_to(root)
 if any(part in EXCLUDED_DIRS for part in r.parts) or path.suffix.lower() in EXCLUDED_SUFFIXES: return False
 if r.parts and r.parts[0]=="data": return True
 if r.as_posix() in ROOT_RUNTIME_INPUTS: return True
 if profile in {"release","tested-code"}: return path.suffix.lower() in RELEASE_SUFFIXES
 raise ValueError(profile)
def canonical_fingerprint_files(root:Path,*,profile:str)->tuple[Path,...]:
 root=root.resolve(); return tuple(sorted((p for p in root.rglob("*") if p.is_file() and _included(root,p,profile)),key=lambda p:p.relative_to(root).as_posix()))
def compute_fingerprint(root:Path,*,profile:str)->dict[str,Any]:
 root=root.resolve(); records={}; agg=hashlib.sha256()
 for p in canonical_fingerprint_files(root,profile=profile):
  rel=p.relative_to(root).as_posix(); dig=sha256_file(p); size=p.stat().st_size; records[rel]={"sha256":dig,"size_bytes":size}; agg.update(rel.encode()); agg.update(b"\0"); agg.update(str(size).encode()); agg.update(b"\0"); agg.update(dig.encode()); agg.update(b"\n")
 coverage="all source/GUI/tests/tools, dependency/configuration inputs, packaged runtime data, and release-facing Markdown inspected by regressions; generated evidence and transient caches excluded" if profile=="tested-code" else "release executable/config/runtime/documentation inventory; generated evidence and transient caches excluded"
 return {"schema_version":SCHEMA_VERSION,"algorithm":ALGORITHM,"profile":profile,"coverage":coverage,"file_count":len(records),"aggregate_sha256":agg.hexdigest(),"files":records}
def compute_release_tree_fingerprint(root:Path)->dict[str,Any]: return compute_fingerprint(root,profile="release")
def compute_tested_code_fingerprint(root:Path)->dict[str,Any]: return compute_fingerprint(root,profile="tested-code")
def fingerprint_mismatches(expected:Mapping[str,Any],actual:Mapping[str,Any])->dict[str,Any]:
 ef=expected.get("files",{}); af=actual.get("files",{}); missing=sorted(set(ef)-set(af)); added=sorted(set(af)-set(ef)); changed={n:{"expected":ef[n],"actual":af[n]} for n in sorted(set(ef)&set(af)) if ef[n]!=af[n]}; metadata={k:{"expected":expected.get(k),"actual":actual.get(k)} for k in ("schema_version","algorithm","profile","coverage","file_count","aggregate_sha256") if expected.get(k)!=actual.get(k)}; return {"missing":missing,"added":added,"changed":changed,"metadata":metadata}
def verify_fingerprint(root:Path,expected:Mapping[str,Any],*,profile:str)->None:
 mm=fingerprint_mismatches(expected,compute_fingerprint(root,profile=profile));
 if any(mm[k] for k in mm): raise SystemExit(f"{profile} fingerprint mismatch: {mm}")
def verify_release_tree_fingerprint(root:Path,expected:Mapping[str,Any])->None: verify_fingerprint(root,expected,profile="release")
def verify_tested_code_fingerprint(root:Path,expected:Mapping[str,Any])->None: verify_fingerprint(root,expected,profile="tested-code")
def main()->None:
 ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parent); ap.add_argument("--profile",choices=("release","tested-code"),default="release"); ap.add_argument("--output",type=Path); ap.add_argument("--verify",type=Path); a=ap.parse_args(); payload=compute_fingerprint(a.root,profile=a.profile)
 if a.verify:
  expected=json.loads(a.verify.read_text()); mm=fingerprint_mismatches(expected,payload);
  if any(mm[k] for k in mm): raise SystemExit(json.dumps(mm,indent=2,sort_keys=True))
  print(f"verified {a.profile} fingerprint: {payload['aggregate_sha256']}"); return
 text=json.dumps(payload,indent=2,sort_keys=True)+"\n"; a.output.write_text(text) if a.output else print(text,end="")
if __name__=="__main__": main()
