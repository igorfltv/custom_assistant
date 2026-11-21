#!/usr/bin/env python3
"""Build a source-only evaluation cache from case directories and client archives.

XML envelopes are inspected for declaration tags before scheduling extraction.
--include-alta-support processes only allowlisted supporting document members
of GTD.ZIP, excluding GTD/INV/KTD/DS*/OPN/docs.xml.
Files and model outputs remain in the chosen private output directory.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.providers import complete
from forma_declaration_agent.analysis import recognize_page
from forma_declaration_agent.documents import archive_members, extract_document, is_declaration_xml, EXTENSIONS, PDF_EXTRACTION_VERSION
from forma_declaration_agent.alta_documents import MAGIC as ALTA_SUPPORT, EXCLUDED as ALTA_RESULTS


def excluded(name):
    return name.upper().startswith('GTD_') or Path(name).suffix.lower() in ALTA_RESULTS or name.lower()=='docs.xml'


def init_worker(output,key):
    global BASE,CONNECTION
    BASE=Path(output)
    CONNECTION={'base_url':'https://api.deepseek.com/v1','secret':key}


def work(task):
    case,path,filename=task
    path=Path(path)
    fingerprint=hashlib.sha256(path.read_bytes()).hexdigest()
    target=BASE/'extracted'/case/(fingerprint+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    stage={'provider':'deepseek','model':'deepseek-flash','vision':True,'max_tokens':65536,'thinking':True,'reasoning_effort':'max'}
    extraction_version = PDF_EXTRACTION_VERSION if path.suffix.lower() == '.pdf' else None
    if target.exists():
        cached=json.loads(target.read_text())
        if cached.get('ocr_profile')==stage and cached.get('extraction_version') == extraction_version:
            return {'case':case,'filename':filename,'status':'cached'}
    calls=[]
    def ocr(locator,image):
        value,trace=recognize_page(image,partial(complete,stage,CONNECTION))
        calls.append({**trace,'stage':'ocr','locator':locator})
        return value
    try:
        segments,warnings=extract_document(path,path.suffix.lower(),filename,recognize=ocr,max_pages=500,max_chars=3_000_000,cache_dir=BASE/'ocr-cache',cache_namespace=json.dumps(stage,sort_keys=True)+':ocr-v1')
        for segment in segments:segment['document_id']=fingerprint
        data={'filename':filename,'sha256':fingerprint,'segments':segments,'warnings':warnings,'calls':calls,'ocr_profile':stage,
              'extraction_version':extraction_version}
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=target.parent,delete=False) as f:json.dump(data,f,ensure_ascii=False)
        Path(f.name).replace(target)
        target.with_name(fingerprint+'.error.json').unlink(missing_ok=True)
        return {'case':case,'filename':filename,'status':'completed','segments':len(segments)}
    except Exception as exc:
        error={'filename':filename,'sha256':fingerprint,'error':type(exc).__name__+': '+str(exc)[:240],'calls':calls}
        target.with_name(fingerprint+'.error.json').write_text(json.dumps(error,ensure_ascii=False))
        return {'case':case,'filename':filename,'status':'failed','error':error['error']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True,type=Path,help='Root containing one directory per case')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--key-file',type=Path)
    parser.add_argument('--case', action='append', help='Extract only the named case (repeatable)')
    parser.add_argument('--workers',type=int,choices=range(1,9),default=2)
    parser.add_argument('--include-alta-support',action='store_true',help='Include only supporting documents from Alta archives; never declarations or declaration workspaces')
    args=parser.parse_args()
    key=args.key_file.read_text().strip() if args.key_file else os.environ['DEEPSEEK_API_KEY']
    os.umask(0o077)
    args.output.mkdir(parents=True,exist_ok=True)
    tasks=[]
    # Staging uses generated names, independent of paths inside client archives.
    with tempfile.TemporaryDirectory(prefix='forma-cases-',dir=args.output) as staging:
        for case in sorted(p for p in args.input.iterdir() if p.is_dir()):
            if args.case and case.name not in args.case:continue
            seen=set()
            for path in sorted(case.rglob('*')):
                if not path.is_file() or excluded(path.name) or path.name.startswith('.'):continue
                if path.suffix.lower() not in EXTENSIONS:continue
                if path.suffix.lower() in {'.zip','.7z'}:
                    if path.name.upper().endswith('.GTD.ZIP') and not args.include_alta_support:continue
                    folder=Path(staging)/str(len(tasks));folder.mkdir(exist_ok=True)
                    candidates=((path.name+'/'+name,source) for name,source in archive_members(path,folder)
                                if not path.name.upper().endswith('.GTD.ZIP') or source.suffix.lower() in ALTA_SUPPORT)
                else:candidates=[(path.name,path)]
                for name,source in candidates:
                    if excluded(Path(name).name) or source.suffix.lower() not in EXTENSIONS:continue
                    if is_declaration_xml(source):continue
                    digest=hashlib.sha256(source.read_bytes()).hexdigest()
                    if digest in seen:continue
                    seen.add(digest)
                    tasks.append((case.name,str(source),name))
        # PDFium is process-isolated; only OCR requests use threads within a worker.
        with ProcessPoolExecutor(max_workers=args.workers,initializer=init_worker,initargs=(str(args.output),key)) as pool:
            for result in pool.map(work,tasks):print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
