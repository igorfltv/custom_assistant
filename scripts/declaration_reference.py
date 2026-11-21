"""Output-only comparison of a generated Alta draft with a specialist's XML."""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import parse
from forma_declaration_agent.evaluation import compare
from forma_declaration_agent.schema import ALL_BINDINGS


@dataclass
class Reference:
    path: Path
    root: ET.Element
    format: str
    source_fields: list | None = None

    def compare(self, actual):
        result = compare(actual, self.root)
        result['reference_format'] = self.format
        if self.source_fields is not None:
            result.update(xml_equal=None, scope='Cross-format comparison of mapped ESAD fields in Alta order.',
                          source_fields=len(self.source_fields),
                          mapped_source_fields=sum(bool(row['alta_path']) for row in self.source_fields))
        return result


def esad_reference(path, root, declaration):
    """Map direct equivalents only. Keep every source leaf, including customs marks."""
    projected = ET.Element('AltaGTD')
    mapped = {}

    def copy_fields(source, target, mapping):
        for key, field in mapping.items():
            for value in source.findall('{*}' + field.replace('/', '/{*}')):
                if not (value.text or '').strip():
                    continue
                parent = target
                tags = key.split('/')
                for tag in tags[:-1]:
                    child = parent.find(tag)
                    parent = child if child is not None else ET.SubElement(parent, tag)
                node = ET.SubElement(parent, tags[-1])
                node.text = value.text.strip()
                mapped[value] = node

    def bindings(source, target, fields):
        copy_fields(source, target, {ALL_BINDINGS[k][1]: v for k, v in fields.items()})

    bindings(declaration, projected, {'direction':'CustomsProcedure', 'procedure':'CustomsModeCode'})
    shipments = declaration.findall('{*}ESADout_CUGoodsShipment')
    if len(shipments) != 1:
        raise ValueError('Expected one goods shipment in ESADout_CU')
    shipment, = shipments
    bindings(shipment, projected, {'origin_country':'OriginCountryCode', 'total_goods':'TotalGoodsNumber',
                                   'packages':'TotalPackageNumber'})
    for tag, fields in [
        ('ESADout_CUConsigment', {'container':'ContainerIndicator', 'dispatch_country':'DispatchCountryCode',
          'destination_country':'DestinationCountryCode', 'border_transport_type':'ESADout_CUBorderTransport/TransportModeCode',
          'inland_transport_type':'ESADout_CUDepartureArrivalTransport/TransportModeCode',
          'departure_transport_country':'ESADout_CUDepartureArrivalTransport/TransportNationalityCode',
          'border_transport_country':'ESADout_CUBorderTransport/TransportNationalityCode'}),
        ('ESADout_CUMainContractTerms', {'currency':'ContractCurrencyCode', 'invoice_total':'TotalInvoiceAmount',
          'trading_country':'TradeCountryCode', 'incoterm':'CUESADDeliveryTerms/DeliveryTermsStringCode',
          'delivery_place':'CUESADDeliveryTerms/DeliveryPlace'})]:
        for section in shipment.findall('{*}'+tag):
            bindings(section, projected, fields)
    for party, role in [('Consignor','consignor'), ('Consignee','consignee'), ('Declarant','declarant'),
                        ('FinancialAdjustingResponsiblePerson','financial_party')]:
        for section in shipment.findall('{*}ESADout_CU'+party):
            fields = {'name':'OrganizationName','registration_id':'RFOrganizationFeatures/OGRN',
                      'tax_id':'RFOrganizationFeatures/INN','country':'SubjectAddressDetails/CountryCode',
                      'city':'SubjectAddressDetails/City','postal_code':'SubjectAddressDetails/PostalCode'}
            bindings(section, projected, {f'{role}.{key}':field for key, field in fields.items()})
    for item in shipment.findall('{*}ESADout_CUGoods'):
        block = ET.SubElement(projected, 'BLOCK')
        fields = {'number':'GoodsNumeric','description':'GoodsDescription','hs_code':'GoodsTNVEDCode',
                  'origin':'OriginCountryCode','gross_weight':'GrossWeightQuantity','net_weight':'NetWeightQuantity',
                  'invoice_amount':'InvoicedCost','customs_value':'CustomsCost','statistical_value':'StatisticalCost'}
        bindings(item, block, {'goods.'+key:field for key, field in fields.items()})
        for document in item.findall('{*}ESADout_CUPresentedDocument'):
            copy_fields(document, ET.SubElement(block, 'G44'),
                        {'G441':'PresentedDocumentModeCode','G442':'PrDocumentNumber',
                         'G443':'PrDocumentDate','G444':'PrDocumentName'})

    def walk(node, path):
        yield node, path
        counts = Counter()
        for child in node:
            name = child.tag.rsplit('}', 1)[-1]
            counts[name] += 1
            yield from walk(child, f'{path}/{name}[{counts[name]}]')

    targets = dict(walk(projected, '/AltaGTD'))
    rows = []
    for node, source in walk(root, '/'+root.tag.rsplit('}', 1)[-1]):
        for key, value in node.attrib.items():
            rows.append({'path':source+'/@'+key, 'value':value, 'alta_path':None})
        if not len(node) and (node.text or '').strip():
            rows.append({'path':source, 'value':node.text.strip(), 'alta_path':targets.get(mapped.get(node))})
    return Reference(path, projected, 'ESADout_CU', rows)


def load_reference(folder):
    xmls = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == '.xml')
    alta = [p for p in xmls if p.name.upper().startswith('GTD_')]
    candidates = []
    for path in alta or xmls:
        try:
            root = parse(path).getroot()
        except ET.ParseError:
            if path in alta:
                raise
            continue
        tag = root.tag.rsplit('}', 1)[-1]
        if root.tag == 'AltaGTD':
            candidates.append(Reference(path, root, 'AltaGTD'))
        elif tag == 'ESADout_CU':
            candidates.append(esad_reference(path, root, root))
        elif tag == 'ED_Container':
            for declaration in root.findall('{*}ContainerDoc/{*}DocBody/{*}ESADout_CU'):
                candidates.append(esad_reference(path, root, declaration))
    if len(candidates) != 1:
        raise ValueError(f'Expected one reference declaration in {folder.name}, found {len(candidates)}')
    return candidates[0]
