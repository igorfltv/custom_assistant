#!/usr/bin/env python3
"""Render a private, standalone HTML summary of source-only evaluation results."""
import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('results',type=Path)
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args()
    rows=[];details=[];summaries=[]
    for path in sorted(args.results.glob('*/report.json')):
        data=json.loads(path.read_text());c=data.get('comparison',{})
        name=path.parent.name;url=quote(name)
        baseline=args.baseline/name/'report.json' if args.baseline else None
        before=json.loads(baseline.read_text()).get('comparison',{}) if baseline and baseline.exists() else {}
        calls=data.get('calls',[]);cached=sum(bool(call.get('cache_hit')) for call in calls)
        summary={'case':name,'status':data['status'],'documents':len(data.get('input_manifest',[])),
                 'headers':f"{c.get('header_matches','—')}/{c.get('header_total',8)}",
                 'actual_items':c.get('actual_items'),'expected_items':c.get('expected_items'),
                 'hs_matches':c.get('hs_code_multiset_matches'),'hs_precision':c.get('hs_code_precision'),'hs_recall':c.get('hs_code_recall'),
                 'baseline_items':before.get('actual_items'),'field_counts':c.get('field_counts',{}),
                 'xml_equal':c.get('xml_equal',False),'new_api_calls':len(calls)-cached,'cached_calls':cached,
                 'extraction_cache_reused':True,'import_performed':False,'ready_for_filing':False}
        summaries.append(summary)
        hs=f"{c.get('hs_code_multiset_matches','—')} / {c.get('expected_items','—')}"
        items=f"{before.get('actual_items','—')} → {c.get('actual_items','—')} / {c.get('expected_items','—')}"
        state='Проект сформирован' if data['status']=='completed' else 'Обработка не завершена'
        rows.append(f'<tr><td>{html.escape(name)}</td><td>{state}</td><td>{summary["documents"]}</td><td>{summary["headers"]}</td><td>{items}</td><td>{hs}</td></tr>')
        checks=''.join(f'<tr><td>{html.escape(h["field"])}</td><td>{html.escape(h["expected"])}</td><td>{html.escape(h["actual"]) or "—"}</td><td>{"Да" if h["match"] else "Нет"}</td></tr>' for h in c.get('header_checks',[]))
        error=f'<p>{html.escape(data["error"])}</p>' if data.get('error') else ''
        artifact=f'<a href="{url}/draft.xml">XML-проект</a> · <a href="{url}/result.json">Все наблюдения и решения</a> · ' if data['status']=='completed' else ''
        details.append(f'<details><summary>{html.escape(name)} — проверенные реквизиты</summary>{error}<p>{artifact}<a href="{url}/report.json">Полный отчёт JSON</a></p><table><tr><th>Реквизит</th><th>Эталон</th><th>Проект</th><th>Совпадает</th></tr>{checks}</table><p>Замечаний к XML: {len(data.get("export_issues",[]))}. Вопросов: {data.get("questions","—")}. Нормативных выводов с цитатами: {data.get("legal_findings","—")}.</p><p>Точность совпадения кодов относительно числа предложенных товаров: {c.get("hs_code_precision","—")}; полнота относительно эталона: {c.get("hs_code_recall","—")}.</p></details>')
        totals=''.join(f'<tr><td>{h["field"]}</td><td>{h["expected"]["sum"]}</td><td>{h["actual"]["sum"]}</td><td>{h["actual"]["present"]} / {c["actual_items"]}</td><td>{"Да" if h["match"] else "Нет"}</td></tr>' for h in c.get('totals_checks',[]))
        counts=''.join(f'<tr><td>{label}</td><td>{before.get("field_counts",{}).get(key,"—")}</td><td>{c.get("field_counts",{}).get(key,"—")}</td></tr>' for key,label in [('matched','Совпадают'),('missing','Отсутствуют'),('different','Различаются'),('extra','Дополнительные')])
        diffs=''.join('<tr>'+''.join('<td>'+html.escape(str(d.get(k) if d.get(k) is not None else '—'))+'</td>' for k in ['path','expected','actual','kind'])+'</tr>' for d in c.get('differences',[])[:120])
        notes=path.parent/'analysis.json'
        analysis='<ul>'+''.join('<li>'+html.escape(note)+'</li>' for note in json.loads(notes.read_text()).get('findings',[]))+'</ul>' if notes.exists() else ''
        extra=f'<h3>Контрольные суммы по товарам</h3><table><tr><th>Поле</th><th>Эталон</th><th>Проект</th><th>Заполнено строк</th><th>Совпадает</th></tr>{totals}</table><p>35 — брутто; 38 — нетто; 42 — стоимость строк; 45 — таможенная стоимость; 46 — статистическая стоимость. Неполная сумма не считается совпадением.</p><h3>Все заполненные XML-поля</h3><table><tr><th>Результат</th><th>До</th><th>После</th></tr>{counts}</table><details><summary>Первые 120 расхождений; полный список — в JSON</summary><table><tr><th>XML-путь</th><th>Эталон</th><th>Проект</th><th>Тип</th></tr>{diffs}</table></details>{analysis}<p>Успешных новых API-вызовов: {len(calls)-cached}; ответов из кэша: {cached}. OCR и текст документов повторно использованы из кэша.</p><p class="muted">SHA-256 конвейера: {html.escape(data.get("pipeline_sha256",""))}; дата: {html.escape(data.get("generated_at",""))}.</p>'
        details[-1]=details[-1][:-10]+extra+'</details>'
    document='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Проверка агента деклараций</title>
<style>body{margin:40px auto;max-width:1120px;padding:0 24px;font:16px/1.55 system-ui,sans-serif;color:#272824;background:#faf9f6}h1{font-size:32px;line-height:1.15}h2{font-size:21px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #deded8;overflow-wrap:anywhere;max-width:480px}th{font-weight:600;background:#f0eee8}a{color:#a94922}.notice{padding:20px;border-left:4px solid #bd592e;background:#fff3e9}details{padding:16px 0;border-bottom:1px solid #deded8}summary{cursor:pointer;font-weight:600}.scroll{overflow:auto}.muted{color:#64675f}code{font-size:.9em}</style>
<p class="muted">Форма · DeepSeek <code>deepseek-flash</code> · локальный прогон</p><h1>Проверка на четырёх комплектах</h1>
<p class="notice"><strong>XML пока не совпадают с эталонами и остаются проектами.</strong> Исправления сопоставления не завершают юридическую группировку, оценку стоимости и заполнение всех граф. Пользователь импортирует итоговый XML самостоятельно; импорт в Альта-ГТД не выполняется.</p>
<div class="scroll"><table><tr><th>Комплект</th><th>Выполнение</th><th>Входных файлов*</th><th>Общие реквизиты</th><th>Строк: до → после / товаров эталона</th><th>Совпавших кодов / товаров эталона</th></tr>'''+''.join(rows)+'''</table></div>
<p class="muted">* Уникальные файлы по содержимому, без архивов готового оформления. Восемь общих реквизитов: направление, процедура, места, валюта, сумма, Incoterms, страны отправления и назначения.</p>
<h2>Как читать результат</h2><p>Сравниваются все непустые XML-листья и атрибуты с сохранением повторных узлов. Суммы, веса и количества нормализуются как десятичные числа; идентификаторы сохраняют ведущие нули. Сопоставление полей товаров идёт по порядку XML, поэтому разная группировка увеличивает число расхождений. Суммы и мультимножества кодов сравниваются независимо от порядка. Регистрационные и служебные сведения готового оформления включены в разницу, но не должны копироваться в новую декларацию.</p><p>Строки коммерческого инвойса и товары ДТ — разные уровни. Меньшее число строк может означать как удаление дублей, так и потерю данных, поэтому проверяются также суммы и первичные документы.</p>
<p>Клиентские документы передавались модели отдельно. GTD_*.xml в оценочном скрипте открывался после генерации; *.GTD.ZIP не использовался. Эти комплекты использовались при разработке и исправлении обработчиков, поэтому это регрессионная проверка, а не независимый тест обобщения.</p>
<h2>Что исправлено</h2><ul><li>Фактические инвойсы отделены от проформ, налоговых счетов-фактур и справок. Копии с подтверждёнными номерами связываются построчно.</li><li>Смешанная Excel-книга сохраняет отдельные таблицы инвойса и упаковочного листа.</li><li>Доставка учитывается отдельным расходом, а не товаром; распределение в стоимость не выполняется автоматически.</li><li>Неподписанная колонка не может стать таможенной стоимостью; варианты описаний сохраняются с источниками.</li></ul>
<h2>Что ещё требуется</h2><ul><li>Разрешить оставшиеся неоднозначные сопоставления и конфликты исходных сведений.</li><li>Группировать товарные строки в товары ДТ с сохранением сумм, количества и массы.</li><li>Проверять классификацию, ставки, льготы и ограничения на дату оформления; заполнить оставшиеся реквизиты и платежи.</li><li>Проверить соответствие XML формату Альта-ГТД без выполнения импорта агентом.</li></ul>
<h2>Подробности по комплектам</h2>'''+''.join(details)+'''<h2>Модели и исправления</h2><p>DeepSeek использован для OCR, извлечения, сопоставления и нормативной проверки. Роли можно разделить в админке. Для сложного сопоставления полезен режим рассуждения; отдельные embedding и reranker пока не подключены — поиск работает на локальном FTS5.</p><p>Исправления проходят проверку администратора и используются как примеры для того же клиента. JSONL предназначен для отдельного обучения; веса модели автоматически не меняются.</p><p class="muted">Нормативные источники архивируются и индексируются по версиям. Полученный снимок не становится автоматически применимой нормой. Все материалы отчёта хранятся локально.</p></html>'''
    (args.results/'index.html').write_text(document)
    (args.results/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
    print(args.results/'index.html')


if __name__=='__main__':main()
