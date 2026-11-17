#!/usr/bin/env python3
"""Audit saved source-only runs against the 54-graph user-facing contract.

Read-only with respect to generation: no model calls, reference access, inferred
values or changes to drafts. Missing applicability decisions count as unexplained,
not as proof that every graph must be filled. Exit 1 means acceptance failed.
Run with the backend virtual environment.
"""
import argparse
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from forma_declaration_agent.catalog import CATALOG, ITEM_GRAPHS
from forma_declaration_agent.schema import ALL_BINDINGS, BINDINGS


ROOT = Path(__file__).resolve().parents[1]
GENERIC_ACTION = "Найдите значение в документах поставки или уточните его у ответственного специалиста и укажите в ответе."


def audit(case):
    report = json.loads((case / 'report.json').read_text())
    if report['status'] != 'completed':
        return {'case': case.name, 'accepted': False, 'status': report['status'],
                'error': report.get('error'), 'graphs': []}
    result = json.loads((case / 'result.json').read_text())
    fields, questions = result['draft']['fields'], result['draft']['questions']
    xml = ET.parse(case / 'draft.xml').getroot()
    indexed = {(f['graph'], f.get('item')): f for f in fields}
    items = sorted({f['item'] for f in fields if f.get('item') is not None})
    article_data = json.loads((ROOT / 'agent/src/forma_declaration_agent/resources/alta_declaration_review.json').read_text())
    articles = {a['graph']: a for a in article_data['articles']}
    extraction_graphs = {g for g, _ in BINDINGS.values()}
    supported_graphs = {g for g, _ in ALL_BINDINGS.values()} | {'5', '32', '44'}
    graphs = []
    for entry in CATALOG:
        graph = entry['number']
        slots = []
        for item in (items or [1]) if graph in ITEM_GRAPHS else [None]:
            field = indexed.get((graph, item), {})
            value = str(field.get('value', '')).strip()
            derived = False
            if graph in {'5', '32'}:
                if graph == '5':
                    value = xml.findtext('G_5_1', '')
                else:
                    value = next((b.findtext('G_32_1', '') for b in xml.findall('BLOCK')
                                  if b.findtext('G_32_1') == str(item)), '')
                derived = bool(value)
            pending = [q for q in questions if (q['graph'], q.get('item')) == (graph, item)]
            issues = [e for e in report['export_issues'] if (e['graph'], e.get('item')) == (graph, item)]
            # Only evidence actually saved by the agent counts as its explanation.
            explained=all(q.get('reason') and q.get('details',{}).get('action') and q.get('details',{}).get('needed_inputs') for q in pending)
            ambiguous=field.get('status') in {'conflict','unverified'} or bool(issues) or any(
                p.get('status') in {'conflict','unverified'} or p.get('requires_source_review') for p in field.get('parts',[]))
            slots.append({'item': item, 'value': value, 'derived_in_xml': derived,
                          'status': field.get('status', 'derived' if derived else 'missing'),
                          'questions': [{'kind': q['kind'], 'component': q.get('component'),
                                         'text': q['text'], 'reason': q['reason'],
                                         'action': q.get('details', {}).get('action', ''),
                                         'needed_inputs':q.get('details',{}).get('needed_inputs',[]),
                                         'legal_references':q.get('details',{}).get('legal_references',[])} for q in pending],
                          'export_issues': issues,
                          'unexplained_empty': not value and not pending,
                          'unambiguous':bool(value) and not ambiguous and not pending,
                          'explained':bool(pending) and explained,
                          'contract_satisfied':(bool(value) and not ambiguous and not pending) or (bool(pending) and explained)})
        present = sum(bool(s['value']) for s in slots)
        unexplained = sum(s['unexplained_empty'] for s in slots)
        article = articles.get(graph, {})
        if present == len(slots):
            diagnosis = 'Есть значения; полнота составных реквизитов и правильность требуют отдельной проверки.'
        elif graph not in supported_graphs:
            diagnosis = 'Нет структурированной поддержки графы в агенте/экспорте. Отсутствие значения не доказывает нехватку документов заказчика.'
        elif graph not in extraction_graphs and graph != '44':
            diagnosis = 'Значение не получено из контекста оформления или расчёта. Эти данные не извлекаются текущим обработчиком документов.'
        else:
            diagnosis = 'Агент не сохранил значение для всех товаров/реквизитов. Нужно проверить извлечение и источники, прежде чем запрашивать документ повторно.'
        if unexplained:
            diagnosis += ' Для пустых ячеек нет ни вопроса, ни объяснения неприменимости.'
        if all(s['unambiguous'] for s in slots):
            diagnosis = 'Значение заполнено; открытых вопросов по этой графе и замечаний к её выгрузке нет.'
        elif all(s['contract_satisfied'] for s in slots):
            diagnosis = ('Нужны уточнения: агент сохранил конкретную причину и перечень вводных. '
                         'Найденные значения показаны рядом; они не считаются окончательными при наличии вопросов.')
        graphs.append({'graph': graph, 'name': entry['name'], 'slots_total': len(slots),
                       'slots_with_value': present, 'unexplained_empty_slots': unexplained,
                       'has_any_value': bool(present),
                       'has_any_question': any(s['questions'] for s in slots),
                       'diagnosis': diagnosis,
                       'inputs_to_check': article.get('inputs', 'Сначала определить применимость графы к выбранному оформлению по нормативному порядку; затем установить необходимые документы.'),
                       'guidance_url': article.get('url'), 'slots': slots})
    silent_export = []
    for issue in report['export_issues']:
        matching = [q for q in questions if q['graph'] == issue['graph'] and q.get('item') == issue.get('item')
                    and q.get('export_issue_kind',q['kind']) == issue['kind'] and (not issue.get('key') or q.get('component') in {None, issue['key']})
                    and (issue['kind']!='mapping' or issue['message'] in q['reason'])]
        if not matching:
            silent_export.append(issue)
    empty_graphs = [g['graph'] for g in graphs if not g['has_any_value'] and not g['has_any_question']]
    generic = sum(q.get('details', {}).get('action') == GENERIC_ACTION for q in questions)
    unexplained_slots = sum(g['unexplained_empty_slots'] for g in graphs)
    failed_slots=[{'graph':g['graph'],'item':s['item']} for g in graphs for s in g['slots'] if not s['contract_satisfied']]
    assert len(graphs) == 54 and len({g['graph'] for g in graphs}) == 54
    calls = report['calls']
    return {'case': case.name, 'status': 'completed',
            'generated_at': report['generated_at'],
            'accepted': not (failed_slots or generic or silent_export or report['input_errors']),
            'documents': len(report['input_manifest']), 'items': len(items),
            'graphs_with_values': sum(g['has_any_value'] for g in graphs),
            'graphs_unambiguous':[g['graph'] for g in graphs if all(s['unambiguous'] for s in g['slots'])],
            'graphs_requiring_input':[g['graph'] for g in graphs if any(s['explained'] for s in g['slots'])],
            'graphs_empty_with_questions': sum(not g['has_any_value'] and g['has_any_question'] for g in graphs),
            'graphs_empty_without_explanation': empty_graphs,
            'unexplained_empty_slots': unexplained_slots, 'generic_missing_questions': generic,
            'contract_failed_slots':failed_slots,
            'unambiguous_slots':sum(s['unambiguous'] for g in graphs for s in g['slots']),
            'explained_slots':sum(s['explained'] for g in graphs for s in g['slots']),
            'export_issues_without_matching_question': silent_export,
            'new_api_calls': sum(not c.get('cache_hit') for c in calls),
            'cached_calls': sum(bool(c.get('cache_hit')) for c in calls),
            'new_api_usage': dict(sum((Counter({k: c.get('usage', {}).get(k, 0) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}) for c in calls if not c.get('cache_hit')), Counter())),
            'reference_used_for_generation': report.get('reference_used_for_generation'),
            'pipeline_sha256': report['pipeline_sha256'], 'graphs': graphs}


def esc(value):
    return html.escape(str(value))


def render(results, destination):
    rows, details = [], []
    for result in results:
        case = result['case']
        if result['status'] != 'completed':
            rows.append(f'<tr><td>{esc(case)}</td><td colspan="5">Обработка не завершена: {esc(result.get("error"))}</td></tr>')
            continue
        rows.append(f'<tr><td><a href="#{case}">{case}</a></td><td>{result["documents"]}</td><td>{result["items"]}</td><td>{result["graphs_with_values"]}</td><td>{result["graphs_empty_with_questions"]}</td><td class="bad">{len(result["graphs_empty_without_explanation"])}</td></tr>')
        graph_rows = []
        for graph in result['graphs']:
            samples = [s for s in graph['slots'] if s['value']][:3]
            values = '<br>'.join(('Товар '+str(s['item'])+': ' if s['item'] is not None else '') + esc(s['value'][:260]) for s in samples)
            value_label = f'{graph["slots_with_value"]}/{graph["slots_total"]} ячеек со значением'
            question_count = sum(len(s['questions']) for s in graph['slots'])
            issue_count = sum(len(s['export_issues']) for s in graph['slots'])
            examples = list(dict.fromkeys(q['reason'] + ' ' + q['action']
                                          for s in graph['slots'] for q in s['questions']))
            # Truncate text before escaping, never generated HTML or an entity.
            actual = '<br>'.join(esc(q[:650]) for q in examples[:3])
            if len(examples) > 3:
                actual += '<p>Остальные объяснения — в полном JSON.</p>'
            guidance = esc(graph['inputs_to_check'])
            if graph['guidance_url']:
                guidance += f' <a href="{esc(graph["guidance_url"])}">Справка</a>'
            graph_rows.append(f'<tr><td>{graph["graph"]}. {esc(graph["name"])}</td><td>{value_label}<p>{values or "—"}</p><small>Вопросов: {question_count}; замечаний экспорта: {issue_count}; пустых без объяснения: {graph["unexplained_empty_slots"]}.</small></td><td>{esc(graph["diagnosis"])}<details><summary>Фактические объяснения агента</summary>{actual or "Нет"}</details></td><td>{guidance}</td></tr>')
        findings_path = destination / case / 'manual-audit.json'
        findings = json.loads(findings_path.read_text()) if findings_path.exists() else []
        finding_html = ''.join(f'<li><strong>{esc(f["title"])}</strong> {esc(f["detail"])}</li>' for f in findings)
        url = quote(case)
        details.append(f'<section id="{case}"><h2>{case}</h2><ul>{finding_html}</ul><p>Пустые графы без объяснения: {", ".join(result["graphs_empty_without_explanation"])}.</p><p>Общих шаблонных запросов без конкретных вводных: {result["generic_missing_questions"]}. Замечаний экспорта без соответствующего вопроса: {len(result["export_issues_without_matching_question"])}. Новых вызовов API: {result["new_api_calls"]}; из кэша: {result["cached_calls"]}.</p><p><a href="{url}/draft.xml">XML-проект</a> · <a href="{url}/result.json">Полный результат агента и источники</a> · <a href="{url}/coverage.json">Проверка всех граф и товаров</a></p><table><thead><tr><th>Графа</th><th>Результат</th><th>Почему нельзя считать заполненной</th><th>Какие вводные проверять</th></tr></thead><tbody>{"".join(graph_rows)}</tbody></table></section>')
    passed = sum(r['accepted'] for r in results)
    documents = sum(r.get('documents', 0) for r in results)
    dates = ', '.join(sorted({datetime.fromisoformat(r['generated_at']).astimezone(ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y')
                             for r in results if r.get('generated_at')}))
    document = f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Повторная проверка 54 граф</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;background:#f8f7f4;color:#252820;max-width:1440px;margin:40px auto;padding:0 24px}}h1{{font-size:34px;line-height:1.2}}h2{{margin-top:50px}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:13px;border-bottom:1px solid #d7d9d0;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eceee5}}td:first-child{{min-width:120px}}td{{max-width:420px}}a{{color:#215c50}}small{{color:#60665b}}.bad{{color:#a52a22;font-weight:650}}.notice{{padding:20px;background:#ffede8;border-left:4px solid #a52a22}}details{{margin-top:10px}}summary{{cursor:pointer}}section{{scroll-margin-top:15px}}</style>
<h1>Из документов заказчика — декларация: проверка 54 граф</h1><p>Повторный прогон · {dates} · DeepSeek deepseek-flash</p>
<p class="notice"><strong>Критерий принятия выполнен: {passed} из {len(results)} комплектов.</strong> Для каждой графы требуется обоснованное значение либо понятное объяснение, почему её нельзя заполнить и какие вводные нужны. Неприменимость графы тоже должна объясняться. Наличие XML само по себе этот тест не закрывает.</p>
<table><tr><th>Пример</th><th>Документов</th><th>Товаров в проекте</th><th>Графы с какими-либо значениями*</th><th>Пустые графы с вопросами</th><th>Пустые графы без объяснения</th></tr>{''.join(rows)}</table>
<p><small>* Включает спорные, частичные значения и рассчитанные экспортом графы 5 и 32. Это не число правильно и полностью заполненных граф. Товарные графы проверены отдельно для каждого товара; сводка выше считает номера граф от 1 до 54.</small></p>
<p>В прогоне {documents} исходных документов; текст и OCR использованы из прежнего кэша. Конвейер выполнен заново, неизменившиеся модельные ответы взяты из кэша; новые вызовы указаны по каждому примеру. Эталон открывается оценочным скриптом после генерации. Это регрессионная проверка, а не независимый тест на новых документах.</p>
<p>Последний столбец — подсказки аудитора из локального учебного обзора, а не сообщения, которые уже выдаёт продукт, и не утверждение об обязательности каждой графы. Отсутствие данных в результате не доказывает их отсутствие в клиентских документах. Полный перечень по каждому товару сохранён в JSON.</p>
<p><a href="coverage.json">Сводный аудит JSON</a> · <a href="index.html">Сравнение XML с эталонами</a></p>{''.join(details)}</html>'''
    (destination / 'coverage.html').write_text(document)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    args = parser.parse_args()
    results = [audit(p.parent) for p in sorted(args.results.glob('*/report.json'))]
    if not results:
        parser.error('No case reports found')
    for result in results:
        (args.results / result['case'] / 'coverage.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    manifest = {'generated_at': datetime.now(timezone.utc).isoformat(),
                'scope': 'Structural lower-bound acceptance audit, not a legal or all-components correctness certification.',
                'cases': results}
    (args.results / 'coverage.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    render(results, args.results)
    for result in results:
        print(json.dumps({k: v for k, v in result.items() if k not in {'graphs', 'export_issues_without_matching_question'}}, ensure_ascii=False))
    raise SystemExit(0 if all(r['accepted'] for r in results) else 1)


if __name__ == '__main__':
    main()
