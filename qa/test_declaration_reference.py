import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from declaration_reference import load_reference


def test_esad_maps_repeated_items_and_register_without_scoring_customs_marks(tmp_path):
    ref = tmp_path/'Container_01.XML'
    ref.write_text('''<ED_Container xmlns="urn:c"><ContainerDoc><DocBody>
      <ESADout_CU xmlns="urn:e"><ESADout_CUGoodsShipment>
      <ESADout_CUGoods><GoodsTNVEDCode>0123456789</GoodsTNVEDCode>
      <ESADout_CUPresentedDocument><PresentedDocumentModeCode>00100</PresentedDocumentModeCode>
      <PrDocumentNumber>N</PrDocumentNumber></ESADout_CUPresentedDocument></ESADout_CUGoods>
      <ESADout_CUGoods><NetWeightQuantity>3</NetWeightQuantity></ESADout_CUGoods>
      </ESADout_CUGoodsShipment></ESADout_CU></DocBody></ContainerDoc>
      <ContainerDoc><DocBody><GTDoutCustomsMark><GoodsNumeric>99</GoodsNumeric></GTDoutCustomsMark>
      </DocBody></ContainerDoc></ED_Container>''')
    reference = load_reference(tmp_path)
    assert reference.root.findtext('BLOCK/G44/G441') == '00100'
    assert reference.root.findtext('BLOCK[2]/G_38_1') == '3'
    report = reference.compare(reference.root)
    assert report['xml_equal'] is None
    assert report['expected_items'] == 2
    assert report['mapped_source_fields'] == 4
    assert report['source_fields'] == 5
    assert reference.source_fields[-1]['alta_path'] is None
    (tmp_path/'Container_02.xml').write_bytes(ref.read_bytes())
    with pytest.raises(ValueError,match='found 2'):
        load_reference(tmp_path)


def test_alta_keeps_its_native_comparison(tmp_path):
    xml = '<AltaGTD><BLOCK><G_33_1>0123456789</G_33_1></BLOCK></AltaGTD>'
    (tmp_path/'GTD_fixture.xml').write_text(xml)
    report = load_reference(tmp_path).compare(ET.fromstring(xml))
    assert report['xml_equal'] and report['reference_format'] == 'AltaGTD'


def test_legacy_input_cache_with_renamed_esad_is_rejected_before_generation(tmp_path):
    import json
    import subprocess

    case = tmp_path/'extracted/example_5'
    case.mkdir(parents=True)
    doc = {'filename':'export.XML','sha256':'local',
           'segments':[{'locator':'{urn:c}ED_Container/{urn:e}ESADout_CU[1]/{urn:e}CustomsModeCode[1]',
                        'filename':'export.XML','text':'10'}], 'warnings':[]}
    (case/'old.json').write_text(json.dumps(doc))
    key = tmp_path/'test-key'
    key.write_text('unused')
    command = Path(__file__).resolve().parents[1]/'scripts/evaluate-declarations.py'
    run = subprocess.run([sys.executable,str(command),'--cache',str(tmp_path),'--output',str(tmp_path/'run'),
                          '--expected',str(tmp_path/'absent'),'--key-file',str(key),'--prepare-only'],
                         capture_output=True,text=True)
    assert run.returncode and 'Declaration in cached XML input' in run.stderr
    assert 'request_stage' not in run.stdout
