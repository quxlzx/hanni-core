"""Read-only measurement/redaction contracts; no native or browser startup."""
import json
import subprocess
import pytest
from scripts.campaign8_native.session import DOM_INVENTORY

def inventory(field):
    script = "\nconst field=JSON.parse(process.argv[1]);\nconst attrs=field.attrs||{};\nconst e={tagName:field.tag||'INPUT',type:field.type||'text',id:field.id||'',\n name:field.name||'',value:field.value||'',tabIndex:field.tabIndex??0,\n selectionStart:field.selectionStart,selectionEnd:field.selectionEnd,\n readOnly:field.readOnly,\n selectedOptions:(field.options||[]).map(textContent=>({textContent})),\n labels:(field.labels||[]).map(textContent=>({textContent})),\n getAttribute:key=>attrs[key]??null,\n getBoundingClientRect:()=>({x:0,y:0,width:80,height:20})};\nObject.defineProperty(e,'innerText',{get:()=>'',set:()=>{throw Error('measurement wrote DOM')}});\nglobalThis.location={href:'http://owned.invalid/'};\nglobalThis.innerWidth=100;globalThis.innerHeight=100;globalThis.devicePixelRatio=1.25;\nglobalThis.getComputedStyle=()=>({visibility:'visible',fontFamily:'Segoe UI'});\nglobalThis.document={title:'Controlled measurement',activeElement:e,\n documentElement:{scrollWidth:100},body:{scrollWidth:100},\n querySelectorAll:selector=>selector.startsWith('button,a,input')?[e]:[]};\nconst expression=JSON.parse(process.argv[2]);\nprocess.stdout.write(JSON.stringify(eval('('+expression+')()')));\n"
    result = subprocess.run(['node', '-e', script, json.dumps(field), json.dumps(DOM_INVENTORY)], check=True, capture_output=True, text=True, timeout=5)
    return json.loads(result.stdout)['controls'][0]

@pytest.mark.parametrize('tag', ['INPUT', 'TEXTAREA', 'SELECT'])
def test_plain_control_value_is_observed_without_mutation(tag):
    result = inventory({'tag': tag, 'value': 'controlled draft', 'options': ['Normal']})
    assert result['value'] == 'controlled draft'
    assert result['valueRedacted'] is False
    assert result['selectedOptionText'] == (['Normal'] if tag == 'SELECT' else None)

@pytest.mark.parametrize('field', [{'type': 'password'}, {'id': 'api-key'}, {'name': 'access_token'}, {'attrs': {'aria-label': 'Client secret'}}, {'labels': ['Authorization token']}])
def test_credential_shaped_values_are_withheld(field):
    result = inventory({**field, 'value': 'synthetic-sensitive-marker'})
    assert result['value'] is None
    assert result['valueRedacted'] is True

def test_selected_and_focus_properties_are_retained():
    result = inventory({'tag': 'BUTTON', 'tabIndex': -1, 'attrs': {'aria-selected': 'true'}})
    assert result['ariaSelected'] == 'true'
    assert result['tabIndex'] == -1
    assert result['value'] is None

def test_sensitive_selected_option_is_withheld():
    result = inventory({'tag': 'SELECT', 'name': 'credential', 'options': ['synthetic-secret']})
    assert result['selectedOptionText'] is None

def test_actual_text_selection_offsets_are_read():
    result = inventory({'tag': 'TEXTAREA', 'value': 'controlled text', 'selectionStart': 2, 'selectionEnd': 8})
    assert (result['selectionStart'], result['selectionEnd']) == (2, 8)

def test_sensitive_text_selection_offsets_are_withheld():
    result = inventory({'type': 'password', 'selectionStart': 0, 'selectionEnd': 10})
    assert result['selectionStart'] is None
    assert result['selectionEnd'] is None

def test_full_read_only_preview_value_is_retained_without_truncation():
    text = '{"controlled":"' + 'x' * 20000 + '"}'
    result = inventory({'tag': 'TEXTAREA', 'value': text, 'readOnly': True, 'selectionStart': 0, 'selectionEnd': len(text)})
    assert result['value'] == text
    assert result['readOnly'] is True
    assert result['selectionEnd'] == len(text)
