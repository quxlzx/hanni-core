"""Conservative visible-text measurement controls; no window/browser startup."""
import json
import subprocess
import pytest
from scripts.campaign8_native.session import DOM_INVENTORY

def visible_text(mode, text='Original controlled row'):
    script = "\nconst [mode,text,expression]=process.argv.slice(1);\nconst normal={left:5,top:5,right:85,bottom:25,width:80,height:20};\nconst rect=mode==='offscreen'?{...normal,top:110,bottom:130}:normal;\nconst parent={tagName:'P',parentElement:null,contains:e=>e===parent,\n getBoundingClientRect:()=>mode==='clipped'?{...normal,right:70}:normal};\nconst node={textContent:text,parentElement:parent};let visited=false;\nglobalThis.location={href:'http://controlled.invalid/'};\nglobalThis.innerWidth=100;globalThis.innerHeight=100;globalThis.devicePixelRatio=1;\nglobalThis.NodeFilter={SHOW_TEXT:4};\nglobalThis.getComputedStyle=()=>({visibility:'visible',display:'block',opacity:mode==='transparent'?'0':'1',overflowX:mode==='clipped'?'hidden':'visible'});\nglobalThis.document={title:'Controlled measurement',activeElement:null,\n body:{scrollWidth:100},documentElement:{scrollWidth:100},querySelectorAll:()=>[],\n createTreeWalker:()=>({nextNode:()=>visited?null:(visited=true,node)}),\n createRange:()=>({selectNodeContents:()=>{},getClientRects:()=>[rect],detach:()=>{}}),\n elementFromPoint:()=>mode==='covered'?{}:parent};\nprocess.stdout.write(JSON.stringify(eval('('+expression+')()')));\n"
    result = subprocess.run(['node', '-e', script, mode, text, DOM_INVENTORY], check=True, capture_output=True, text=True, timeout=5)
    return json.loads(result.stdout)['visibleText']

def test_original_visible_text_is_read_without_assignment():
    assert visible_text('visible') == 'Original controlled row'

@pytest.mark.parametrize('mode', ['offscreen', 'clipped', 'covered', 'transparent'])
def test_nonvisible_rows_are_withheld(mode):
    assert visible_text(mode) == ''

def test_visible_text_is_bounded():
    assert len(visible_text('visible', 'x' * 20000)) == 12000
