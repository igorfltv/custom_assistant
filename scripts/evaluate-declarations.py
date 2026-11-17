#!/usr/bin/env python3
"""Source-only evaluation. Reference declarations never enter a model request.

Input: an extracted-document cache made by the document handlers; --expected is
opened exclusively AFTER all model calls and serialization for a case finish.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.providers import complete
from forma_declaration_agent.pipeline import prepare_dossier, fill_from_dossier
from forma_declaration_agent.dossier import ShipmentDossier
from forma_declaration_agent.alta import export
from forma_declaration_agent.errors import ResponseLimitError, ResponseInterruptedError
from forma_declaration_agent.evaluation import compare
from forma_declaration_agent.alta_documents import EXCLUDED
from forma_declaration_agent.references import register_documents
from forma_declaration_agent.pipeline import call_json


class LedgerComplete(Exception):
    """Explicit diagnostic stop before document registration and legal review."""


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--expected',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--key-file',type=Path)
    parser.add_argument('--case',action='append')
    parser.add_argument('--ledger-only',action='store_true',help='Diagnostic checkpoint only; no XML or reference comparison')
    parser.add_argument('--prepare-only',action='store_true',help='Save source-only dossiers without reading references')
    parser.add_argument('--dossier-dir',type=Path,help='Reuse saved source-only dossiers; validate their input document hashes')
    parser.add_argument('--model-cache',type=Path,help='Shared content-addressed response cache; prompts and model configuration are hashed')
    parser.add_argument('--allow-alta-support',action='store_true',help='Separate archive-assisted diagnostic; never the independent loose-document benchmark')
    parser.add_argument('--refresh-register',action='store_true',help='Re-read presented document headers in a reused dossier, retaining physical ledger')
    parser.add_argument('--thinking',choices=['on','off'],default='on',help='Explicit benchmark profile; default preserves Thinking enabled')
    parser.add_argument('--reasoning-effort',choices=['low','medium','high','max'],default='max')
    parser.add_argument('--max-tokens',type=int,help='Response budget; defaults to 65536 with Thinking, 32768 without it')
    args=parser.parse_args()
    os.umask(0o077)
    code_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'agent/src/forma_declaration_agent').glob('*.py')))+(ROOT/'backend/app/providers.py').read_bytes()).hexdigest()
    key=args.key_file.read_text().strip() if args.key_file else os.environ['DEEPSEEK_API_KEY']
    connection={'base_url':'https://api.deepseek.com/v1','secret':key}
    args.output.mkdir(parents=True,exist_ok=True)
    response_cache=args.model_cache or args.output/'model-cache';response_cache.mkdir(parents=True,exist_ok=True)
    model_stage={'provider':'deepseek','model':'deepseek-flash','vision':False,'thinking':args.thinking=='on'}
    if model_stage['thinking']:model_stage['reasoning_effort']=args.reasoning_effort
    model_stage['max_tokens']=args.max_tokens or (65536 if model_stage['thinking'] else 32768)
    classification_profile={'model':model_stage['model'],'thinking':model_stage['thinking']}
    if model_stage['thinking']:
        classification_profile.update(reasoning_effort=args.reasoning_effort,max_tokens=model_stage['max_tokens'])
    elif model_stage['max_tokens']!=32768:classification_profile['max_tokens']=model_stage['max_tokens']
    results=[]
    for folder in sorted((args.cache/'extracted').iterdir()):
        if args.case and folder.name not in args.case: continue
        case_out=args.output/folder.name;case_out.mkdir(exist_ok=True)
        segments=[];warnings=[];manifest=[];ocr_calls=[]
        for path in sorted(folder.glob('*.json')):
            if path.name.endswith('.error.json'): continue
            document=json.loads(path.read_text())
            name=document['filename'].replace('\\','/');basename=name.rsplit('/',1)[-1]
            if Path(basename).suffix.lower() in EXCLUDED or basename.lower()=='docs.xml' or basename.upper().startswith('GTD_') or name.lower().endswith('.gtd.zip'):
                raise ValueError('Reference declaration found among input documents')
            if '.gtd.zip/' in name.lower() and not args.allow_alta_support:
                raise ValueError('Archive-assisted inputs require --allow-alta-support and a separate evaluation')
            segments.extend(document['segments']);warnings.extend(document['warnings']);ocr_calls.extend(document.get('calls',[]))
            manifest.append({'filename':document['filename'],'sha256':document['sha256'],'segments':len(document['segments'])})
        errors=[json.loads(p.read_text()) for p in folder.glob('*.error.json')]
        def call(role,system,text):
            stage=dict(model_stage)
            fingerprint=hashlib.sha256(json.dumps([stage,system,text],ensure_ascii=False).encode()).hexdigest()
            path=response_cache/(fingerprint+'.json')
            if path.exists():
                value=json.loads(path.read_text())
                if value.get('error')=='output_limit':raise ResponseLimitError('Cached output limit; use smaller batch')
                if value.get('error')=='interrupted':raise ResponseInterruptedError('Previous response interrupted; use compact batch')
                return value['result'],{**value['trace'],'cache_hit':True}
            print(json.dumps({'case':folder.name,'request_stage':role,'input_chars':len(text),'request_hash':fingerprint[:12]},ensure_ascii=False),flush=True)
            try:
                result,trace=complete(stage,connection,system,text)
            except ResponseLimitError:
                path.write_text(json.dumps({'error':'output_limit'}))
                raise
            except ResponseInterruptedError:
                path.write_text(json.dumps({'error':'interrupted'}))
                raise
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=response_cache,delete=False) as f:
                json.dump({'result':result,'trace':trace},f,ensure_ascii=False)
            Path(f.name).replace(path)
            print(json.dumps({'case':folder.name,'stage':role,'seconds':trace['seconds'],'usage':trace['usage']},ensure_ascii=False),flush=True)
            return result,trace
        try:
            def checkpoint(phase,payload):
                (case_out/(phase+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2))
                print(json.dumps({'case':folder.name,'phase':phase,'items':len(payload.get('groups',payload.get('decisions',[])))},ensure_ascii=False),flush=True)
                if args.ledger_only and phase=='ledger':raise LedgerComplete()
            dossier_path=args.dossier_dir/folder.name/'dossier.json' if args.dossier_dir else None
            preparation_calls=[]
            if dossier_path and dossier_path.exists():
                dossier=ShipmentDossier.model_validate_json(dossier_path.read_text())
                if {s['document_id'] for s in dossier.segments}!={s['document_id'] for s in segments}:
                    raise ValueError('Saved dossier does not match input document hashes')
                if args.refresh_register:
                    dossier.presented_documents=register_documents(dossier.segments,call,preparation_calls,call_json)
            else:
                dossier=prepare_dossier(segments,complete=call,calls=preparation_calls)
            (case_out/'dossier.json').write_text(dossier.model_dump_json(indent=2))
            if args.prepare_only:
                report={'case':folder.name,'status':'prepared','input_manifest':manifest,'input_errors':errors,
                        'calls':preparation_calls,'reference_used_for_generation':False,'physical_rows':len(dossier.groups),
                        'generated_at':datetime.now(timezone.utc).isoformat(),'pipeline_sha256':code_hash}
                (case_out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));results.append(report)
                print(json.dumps({'case':folder.name,'status':'prepared','rows':len(dossier.groups)}),flush=True)
                continue
            output=fill_from_dossier(dossier,[],complete=call,data_dir=args.cache,checkpoint=checkpoint,
                classification_cache_dir=response_cache/'classification',classification_profile=classification_profile)
            output.calls=preparation_calls+output.calls
            payload,issues=export(output.draft.fields)
            (case_out/'draft.xml').write_bytes(payload)
            (case_out/'result.json').write_text(json.dumps(asdict(output),ensure_ascii=False,indent=2))
            # Reference access starts here, after generation is finished.
            expected_path=next((args.expected/folder.name).glob('GTD_*.xml'))
            comparison=compare(ET.fromstring(payload),ET.parse(expected_path).getroot())
            report={'case':folder.name,'status':'completed','input_manifest':manifest,'input_errors':errors,'extraction_warnings':warnings,'export_issues':issues,'comparison':comparison,'ocr_calls':ocr_calls,'calls':output.calls,'questions':len(output.draft.questions),'legal_findings':len(output.legal_findings),'model':'deepseek-flash','reference_used_for_generation':False,'output_target':'alta_gtd_xml','import_performed':False,'extraction_cache_reused':True}
        except LedgerComplete:
            report={'case':folder.name,'status':'ledger_only','input_manifest':manifest,'reference_used_for_generation':False}
        except Exception as exc:
            report={'case':folder.name,'status':'failed','error':type(exc).__name__+': '+str(exc)[:500],'input_manifest':manifest,'input_errors':errors}
        report.update(generated_at=datetime.now(timezone.utc).isoformat(),pipeline_sha256=code_hash,
                      model_profile=model_stage,
                      input_scope='archive_assisted' if args.allow_alta_support else 'loose_documents')
        (case_out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));results.append(report)
        summary={k:v for k,v in report.get('comparison',{}).items() if k in {'actual_items','expected_items','header_matches','hs_code_multiset_matches','xml_equal','field_counts'}}
        print(json.dumps({'case':folder.name,'status':report['status'],'comparison':summary,'error':report.get('error')},ensure_ascii=False),flush=True)
    results=[json.loads(path.read_text()) for path in sorted(args.output.glob('*/report.json'))]
    (args.output/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
