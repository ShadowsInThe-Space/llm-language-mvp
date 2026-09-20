# ruff: noqa: E501
"""Small deterministic JavaScript target for A1 differential tests."""

from __future__ import annotations

import json
from typing import Any

from llmlang.a1.ir import validate_module


def emit_javascript(module: dict[str, Any], entry: str, arguments: list[Any]) -> str:
    """Emit a self-contained target program that writes one canonical JSON result."""
    validate_module(module)
    document = json.dumps(module, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    inputs = json.dumps(arguments, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"""'use strict';
const moduleIR={document}; const initialArgs={inputs};
const functions=Object.fromEntries(moduleIR.functions.map(f=>[f.name,f]));
function get(env,x){{return x&&typeof x==='object'&&Object.keys(x).length===1&&'ref' in x?env[x.ref]:x;}}
function call(name,args){{
 const f=functions[name]; if(!f) throw new Error('E_A1_CALL');
 const env=Object.fromEntries(f.params.map((p,i)=>[p.name,args[i]]));
 for(const i of f.body){{ let v;
  switch(i.op){{
   case 'const': v=i.value; break;
   case 'record_make': v={{record:i.record,fields:Object.fromEntries(Object.entries(i.fields).map(([k,x])=>[k,get(env,x)]))}}; break;
   case 'record_get': {{const r=get(env,i.value); if(r.record!==i.record) throw new Error('E_A1_NOMINAL'); v=r.fields[i.field]; break;}}
   case 'variant_make': v={{variant:i.variant,tag:i.tag,value:get(env,i.value)}}; break;
   case 'match_value': {{const x=get(env,i.value); v=get(env,i.arms[x.tag]); break;}}
   case 'list_empty': v={{list:[],capacity:i.capacity}}; break;
   case 'list_append': {{const x=get(env,i.list),item=get(env,i.value); v=x.list.length>=x.capacity?{{tag:'Err',value:{{tag:'CapacityError'}}}}:{{tag:'Ok',value:{{list:[...x.list,item],capacity:x.capacity}}}}; break;}}
   case 'list_index': {{const x=get(env,i.list),n=get(env,i.index); v=Number.isInteger(n)&&n>=0&&n<x.list.length?{{tag:'Some',value:x.list[n]}}:{{tag:'None',value:null}}; break;}}
   case 'bounded_map': {{const x=get(env,i.list); v={{list:x.list.map(y=>call(i.callback,[y])),capacity:x.capacity}}; break;}}
   case 'bounded_fold': {{const x=get(env,i.list); v=x.list.reduce((a,y)=>call(i.callback,[a,y]),get(env,i.initial)); break;}}
   case 'text_utf8_bytes': v=Buffer.byteLength(get(env,i.value),'utf8'); break;
   case 'text_codepoint_count': v=Array.from(get(env,i.value)).length; break;
   case 'text_prefix_codepoints': v=Array.from(get(env,i.value)).slice(0,get(env,i.count)).join(''); break;
   case 'text_concat': v=get(env,i.left)+get(env,i.right); if(Buffer.byteLength(v,'utf8')>i.capacity) throw new Error('E_A1_TEXT_CAPACITY'); break;
   case 'refine_nat': v=get(env,i.value); if(!Number.isSafeInteger(v)||v<0) throw new Error('E_A1_REFINEMENT'); break;
   case 'add': v=get(env,i.left)+get(env,i.right); break;
   case 'call': v=call(i.callee,(i.args||[]).map(x=>get(env,x))); break;
   default: throw new Error('E_A1_OP');
  }} env[i.dest]=v;
 }} return env[f.return];
}}
process.stdout.write(JSON.stringify(call({json.dumps(entry)},initialArgs))+'\\n');
"""
