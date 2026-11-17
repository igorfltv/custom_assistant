#!/usr/bin/env python3
"""Exhaustive, OUTPUT-ONLY reference audit; never imported by generation.

Enumerates every reference XML leaf/attribute, all 54 graphs and every goods
block. Literal source hits are diagnostics, never proof of legal applicability.
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from forma_declaration_agent.catalog import CATALOG
from forma_declaration_agent.evaluation import leaves, comparable, compare
from forma_declaration_agent.schema import ALL_BINDINGS

XML_BINDINGS=defaultdict(list)
for key,(_,xml_path) in ALL_BINDINGS.items():
    if xml_path:XML_BINDINGS[xml_path].append(key)


def binding_for(path):
    tags=[part.split('[')[0] for part in path.split('/') if part]
    if tags and tags[0]=='AltaGTD':tags=tags[1:]
    if tags and tags[0]=='BLOCK':tags=tags[1:]
    binding=XML_BINDINGS.get('/'.join(tags),[])
    if binding:return {'kind':'direct_binding','keys':binding}
    if tags and (tags[0] in {'G44','G_5_1','G_32_1','G_22_1'} or tags[:2]==['TXT','TEXT']):
        return {'kind':'structured_export','keys':[]}
    return {'kind':'no_explicit_binding','keys':[]}


def normalized(value):
    return ' '.join(str(value).casefold().split())


class Sources:
    def __init__(self, folder, *, archive=False):
        self.rows=[];self.postings=defaultdict(set);self.memo={}
        for path in sorted(folder.glob('*.json')):
            if path.name.endswith('.error.json'):continue
            document=json.loads(path.read_text())
            if archive and '.gtd.zip/' not in document['filename'].lower():continue
            for segment in document['segments']:
                i=len(self.rows);text=normalized(segment['text'])
                self.rows.append((segment,text))
                for word in set(re.findall(r'[\w.-]{4,}',text)):self.postings[word].add(i)

    def find(self,value):
        query=normalized(value)
        if query in self.memo:return self.memo[query]
        # Single numbers, countries and common abbreviations give false attribution.
        if len(query)<8 or not re.search(r'[^\d\s.,-]',query) and len(query)<10:return []
        words=set(re.findall(r'[\w.-]{4,}',query))
        candidates=min((self.postings[w] for w in words),key=len,default=set())
        result=[]
        for i in sorted(candidates):
            segment,text=self.rows[i]
            if query not in text:continue
            result.append({k:segment[k] for k in ('document_id','filename','locator')})
            if len(result)==3:break
        self.memo[query]=result
        return result


def graph_for(path):
    tags=[part.split('[')[0] for part in path.split('/')]
    # Historical Alta names need the vendor mapping, not a guess from digits.
    if any(t in {'G_28_12','G_28_21'} for t in tags):return None
    if 'G44' in tags:return '44'
    if 'TOVG' in tags or 'TXT' in tags:return '31'
    for tag in tags:
        match=re.match(r'G_(\d+)',tag)
        if match and 1<=int(match[1])<=54:return match[1]
    return None


def category(path,graph):
    tags=[part.split('[')[0] for part in path.split('/')]
    if any(t.startswith(('___','D_','REG','CREATEDATE','PARENT_DOC','C_','ED_')) or t in {'C','PRICES','FACE','BACK','DOCTEXT','CHK_STAT'} for t in tags):return 'service_or_customs_result'
    if any(t.startswith('@') for t in tags):return 'xml_attribute'
    if graph=='7':return 'registration_or_reference_number'
    if graph in {'3','5','12','32','45','46','47'}:return 'calculation_or_derived'
    if graph in {'23','24','28','29','30','36','37','39','40','43','48','49','50','51','52','53','54'}:return 'filing_context_or_rule'
    return 'document_content' if graph else 'unmapped_xml'


def explain(row):
    if row['status']=='match':return 'Совпадает после нормализации пробелов/числового формата; это не юридическое подтверждение.'
    if row['category']=='service_or_customs_result':return 'Служебный реквизит или результат оформления: не переносить из эталона в новую ДТ.'
    if row['category']=='xml_attribute':return 'Атрибут формата/представления. Проверять по версии импортного формата, отдельно от товарных фактов.'
    if row['category']=='unmapped_xml':return 'Реквизит сохранён в аудите, но соответствие печатной графе/маппингу Альта не подтверждено. Нужна проверка формата, не подбор значения из эталона.'
    if row['loose_source_hits']:return 'Точное значение найдено в отдельном исходном документе: проверить извлечение, роль документа, привязку и XML-маппинг.'
    if row['archive_source_hits']:return 'Точное значение найдено в оформленном документе архива. Проверить независимость/редакцию источника до использования как входа.'
    if row['category']=='calculation_or_derived':return 'Проверить исходные суммы, группировку, дату/курс и правило расчёта; значение эталона не использовать как вход.'
    if row['category']=='filing_context_or_rule':return 'Проверить контекст подачи, применимость и документы на дату оформления; простой поиск текста не установил источник.'
    return 'Не совпадает либо не заполнено. Проверить извлечение и сопоставление строк; отсутствие буквального совпадения не доказывает отсутствие сведений.'


def audit(case,expected_dir,actual_dir,baseline_dir,sources_dir,expanded_dir):
    expected_path=next((expected_dir/case).glob('GTD_*.xml'))
    expected=ET.parse(expected_path).getroot()
    actual=ET.parse(actual_dir/case/'draft.xml').getroot()
    baseline=ET.parse(baseline_dir/case/'draft.xml').getroot()
    loose=Sources(sources_dir/'extracted'/case)
    archive=Sources(expanded_dir/'extracted'/case,archive=True) if expanded_dir else None
    actual_values={p:(v,t) for p,v,t in leaves(actual)}
    rows=[]
    for path,value,tag in leaves(expected):
        got=actual_values.get(path,(None,None))[0]
        graph=graph_for(path);kind=category(path,graph)
        item=re.search(r'/BLOCK\[(\d+)\]',path)
        row={'path':path,'graph':graph,'reference_item':int(item[1]) if item else None,
             'expected':value,'actual_same_xml_position':got,'category':kind,
             'xml_adapter':binding_for(path),
             'status':'missing' if got is None else 'match' if comparable(value,tag)==comparable(got,tag) else 'different',
             'loose_source_hits':loose.find(value) if kind not in {'service_or_customs_result','xml_attribute'} else [],
             'archive_source_hits':archive.find(value) if archive and kind not in {'service_or_customs_result','xml_attribute'} else []}
        row['analysis']=explain(row);rows.append(row)
    graphs=[]
    for entry in CATALOG:
        selected=[r for r in rows if r['graph']==entry['number']]
        graphs.append({**entry,'reference_leaves':len(selected),'states':dict(Counter(r['status'] for r in selected)),
                       'adapter_bindings':dict(Counter(r['xml_adapter']['kind'] for r in selected if r['category'] not in {'xml_attribute','service_or_customs_result'})),
                       'loose_literal_hits':sum(bool(r['loose_source_hits']) for r in selected),
                       'archive_literal_hits':sum(bool(r['archive_source_hits']) for r in selected),
                       'assessment':'В эталоне нет непустых реквизитов этой графы; это не универсальная неприменимость.' if not selected else
                       'Все реквизиты совпали по той же позиции XML.' if all(r['status']=='match' for r in selected) else
                       'Есть расхождения; подробное объяснение и источники перечислены для каждого XML-реквизита.',
                       'paths':[r['path'] for r in selected]})
        if entry['number'] in {'24','28'} and any(expected.find(tag) is not None for tag in ('G_28_12','G_28_21')):
            graphs[-1]['assessment']='В XML есть исторические теги G_28_12/G_28_21. Их привязка к печатным графам не подтверждена спецификацией; они включены в раздел unmapped_leaves, а не объявлены отсутствующими.'
    ablocks=actual.findall('BLOCK');goods=[]
    for i,block in enumerate(expected.findall('BLOCK'),1):
        code=block.findtext('G_33_1','');origin=block.findtext('G_34_1','')
        candidates=[j for j,b in enumerate(ablocks,1) if b.findtext('G_33_1')==code and b.findtext('G_34_1','')==origin]
        selected=[r for r in rows if r['reference_item']==i]
        goods.append({'reference_item':i,'hs_code':code,'origin':origin,'description':block.findtext('G_31/NAME',''),
            'same_code_origin_actual_items':candidates,'alignment':'unique_code_origin' if len(candidates)==1 else 'ambiguous_or_missing',
            'reference_leaves':len(selected),'positional_states':dict(Counter(r['status'] for r in selected)),
            'values':[{ 'tag':tag,'expected':block.findtext(tag),
                       'actual_unique_code_origin':ablocks[candidates[0]-1].findtext(tag) if len(candidates)==1 else None,
                       'match':len(candidates)==1 and bool(block.findtext(tag)) and comparable(block.findtext(tag),tag)==comparable(ablocks[candidates[0]-1].findtext(tag,'') or '',tag)}
                      for tag in ('G_35_1','G_38_1','G_42_1','G_43_1','G_45_1','G_46_1')],
            'assessment':'Сравнить значения единственного кандидата; одинаковые код/страна не доказывают тождество состава.' if len(candidates)==1 else
                         'Однозначного соответствия товара нет: сначала исправить классификацию/группировку, затем сравнивать его реквизиты.'})
    generated=json.loads((actual_dir/case/'result.json').read_text())
    registry=generated.get('presented_documents',[])
    document_checks={}
    def number(value):return re.sub(r'\s','',normalized(value or ''))
    for i,block in enumerate(expected.findall('BLOCK'),1):
        for d in block.findall('G44'):
            identity=(d.findtext('G441',''),d.findtext('G442',''),d.findtext('G443',''))
            if identity not in document_checks:
                candidates=[r for r in registry if number(r.get('number'))==number(identity[1])]
                typed=[r for r in candidates if r.get('type_code')==identity[0]]
                document_checks[identity]={'type_code':identity[0],'number':identity[1],'date':identity[2],
                    'title':d.findtext('G444',''),'reference_items':[],
                    'registry_status':'type_number_date_match' if any((r.get('date') or '')==identity[2] for r in typed) else
                                      'type_number_match_date_differs' if typed else 'number_found_type_differs' if candidates else 'not_registered',
                    'registry_candidates':[{k:r.get(k) for k in ('filename','kind','title','type_code','number','date')} for r in candidates],
                    'loose_literal_hits':loose.find(identity[1]),
                    'archive_literal_hits':archive.find(identity[1]) if archive else []}
            document_checks[identity]['reference_items'].append(i)
    assert len(graphs)==54 and len(rows)==sum(1 for _ in leaves(expected))
    return {'case':case,'reference_path':str(expected_path),'reference_used_for_generation':False,
        'method':'All reference nonempty leaves and attributes; positional comparison is sensitive to grouping/order. Literal source search is diagnostic only. Goods code/origin matching is separate and never forces grouping.',
        'before':compare(baseline,expected),'after':compare(actual,expected),'graphs':graphs,'goods':goods,'leaves':rows,
        'reference_documents':list(document_checks.values()),
        'source_review':generated.get('source_review',{}),
        'unmapped_leaves':[r['path'] for r in rows if r['graph'] is None],
        'source_segments':{'loose':len(loose.rows),'archive':len(archive.rows) if archive else 0}}


def cell(value):return str(value).replace('|','\\|').replace('\n',' ').replace('\r',' ')


def render(result,folder):
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    lines=[f"# {result['case']}: полный аудит эталонной декларации",'',
        'Эталон используется только после генерации. Сравнение по XML-позиции чувствительно к порядку и составу групп. Буквальное попадание в документ — ориентир для проверки, не доказательство применимости.', '',
        f"[Все реквизиты, значения и найденные источники]({(folder/'audit.json').resolve()}).", '',
        'Графы индексируются по тегам XML и известным таблицам G44/TOVG/TXT. Неоднозначные исторические теги формата оставлены в unmapped_leaves; отсутствие записи под номером графы не считается доказательством её неприменимости.', '',
        '| Графа | Название | Реквизитов эталона | Совпало | Отличается | Нет | Значение найдено отдельно / в архиве |',
        '|---|---|---:|---:|---:|---:|---:|']
    for g in result['graphs']:
        s=g['states'];lines.append(f"| {g['number']} | {g['name']} | {g['reference_leaves']} | {s.get('match',0)} | {s.get('different',0)} | {s.get('missing',0)} | {g['loose_literal_hits']} / {g['archive_literal_hits']} |")
    lines+=['','## Контроль сумм независимо от порядка товаров','',
            'Сумма частично заполненной графы не считается восстановленным итогом. Совпадение итога само по себе не подтверждает распределение по товарам.', '',
            '| Реквизит | Эталон | До | После | После заполнено / всего | Итог совпадает |',
            '|---|---:|---:|---:|---|---|']
    before_totals={r['field']:r for r in result['before']['totals_checks']}
    for check in result['after']['totals_checks']:
        tag=check['field'];got=check['actual'];old=before_totals[tag]['actual']
        lines.append(f"| {tag} | {check['expected']['sum']} | {old['sum']} | {got['sum']} | {got['present']} / {result['after']['actual_items']} | {'да' if check['match'] else 'нет'} |")
    lines+=['','## Каждый товар эталона','',
            '| № | Код / страна | Товары проекта с тем же кодом и страной | Нетто: эталон → проект | Цена: эталон → проект | Описание эталона |',
            '|---|---|---|---|---|---|']
    for g in result['goods']:
        vals={v['tag']:v for v in g['values']}
        def val(tag):
            v=vals[tag];return cell(v['expected'])+' → '+cell(v['actual_unique_code_origin'] or 'нет однозначного соответствия')
        lines.append(f"| {g['reference_item']} | {g['hs_code']} / {g['origin']} | {', '.join(map(str,g['same_code_origin_actual_items'])) or '—'} | {val('G_38_1')} | {val('G_42_1')} | {cell(g['description'])} |")
    lines+=['','## Документы графы 44 без повторов по товарам','',
            'Сопоставление по номеру и виду отдельно от порядка XML. Наличие в реестре ещё не подтверждает применимость ко всем товарам.', '',
            '| Код | Документ | Номер / дата | Результат сопоставления реестра | Найденный исходный файл |',
            '|---|---|---|---|---|']
    for d in result['reference_documents']:
        filenames=', '.join(dict.fromkeys(r['filename'] for r in d['registry_candidates'])) or '—'
        lines.append(f"| {d['type_code']} | {cell(d['title'])} | {cell(d['number'])} / {d['date']} | {d['registry_status']} | {cell(filenames)} |")
    lines+=['','## Разбор реквизитов','',
            'Для каждого непустого реквизита сохранены ожидаемое и полученное значение, диагноз и точные ссылки на исходный файл/локатор в JSON. Ни один XML-реквизит не исключён из аудита. Служебные поля и результаты выпуска отмечены отдельно.', '']
    for g in result['graphs']:
        lines += [f"### {g['number']}. {g['name']}",'',g['assessment'],'']
        selected=[r for r in result['leaves'] if r['graph']==g['number']]
        if g['adapter_bindings']:
            b=g['adapter_bindings']
            lines += [f"Явное соответствие реквизиту агента: {b.get('direct_binding',0)}; отдельная обработка экспорта: {b.get('structured_export',0)}; нет отдельного соответствия в адаптере: {b.get('no_explicit_binding',0)}. Последнее требует проверки формата: среди таких тегов могут быть дубли представления, а не обязательные данные.",'']
        headers=[r for r in selected if r['reference_item'] is None and r['category'] not in {'xml_attribute','service_or_customs_result'}]
        if headers:
            lines += ['| XML-реквизит | Эталон | Проект | Состояние | Буквальное совпадение в источнике |',
                      '|---|---|---|---|---|']
            for row in headers:
                hits=row['loose_source_hits'] or row['archive_source_hits']
                label='; '.join(h['filename']+' — '+h['locator'] for h in hits) or 'не установлено поиском'
                if not row['loose_source_hits'] and row['archive_source_hits']:label='архив: '+label
                lines.append(f"| {cell(row['path'])} | {cell(row['expected'])} | {cell(row['actual_same_xml_position'] or '—')} | {row['status']} | {cell(label)} |")
            lines.append('')
        for explanation,count in Counter(r['analysis'] for r in selected).items():lines.append(f'- {count}: {explanation}')
        lines.append('')
    (folder/'audit.md').write_text('\n'.join(lines))


def main():
    p=argparse.ArgumentParser()
    for name in ('expected','actual','baseline','sources','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--expanded',type=Path);p.add_argument('--case',action='append')
    args=p.parse_args();summaries=[]
    for case in sorted(args.expected.glob('example_*')):
        if args.case and case.name not in args.case:continue
        result=audit(case.name,args.expected,args.actual,args.baseline,args.sources,args.expanded)
        render(result,args.output/case.name)
        summary={'case':case.name,'reference_leaves':len(result['leaves']),'graphs':len(result['graphs']),'goods':len(result['goods']),
                 'before':{k:result['before'][k] for k in ('actual_items','hs_code_multiset_matches','field_counts','totals_checks')},
                 'after':{k:result['after'][k] for k in ('actual_items','hs_code_multiset_matches','field_counts','totals_checks')}}
        summaries.append(summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
    (args.output/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
