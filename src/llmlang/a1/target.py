# ruff: noqa: E501
"""Small deterministic JavaScript target for A1 differential tests."""

from __future__ import annotations

import json
from typing import Any

from llmlang.a1.ir import validate_module

MAX_SAFE_INTEGER = 9_007_199_254_740_991


class A1TargetError(ValueError):
    """A target-side value cannot be represented without semantic loss."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _reject_unsafe_integers(value: object, path: str = "module") -> None:
    """Reject integers before JSON embeds them as lossy JavaScript Numbers."""

    if type(value) is int and abs(value) > MAX_SAFE_INTEGER:
        raise A1TargetError(
            "E_A1_UNSAFE_INTEGER",
            f"{path} exceeds JavaScript's exact integer range",
        )
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_unsafe_integers(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_unsafe_integers(item, f"{path}[{index}]")


def emit_javascript(module: dict[str, Any], entry: str, arguments: list[Any]) -> str:
    """Emit a self-contained target program that writes one canonical JSON result."""
    validate_module(module)
    _reject_unsafe_integers(module)
    _reject_unsafe_integers(arguments, "arguments")
    document = json.dumps(module, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    inputs = json.dumps(arguments, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"""'use strict';
const moduleIR={document}; const initialArgs={inputs};
const functions=Object.fromEntries(moduleIR.functions.map(f=>[f.name,f]));
const MAX_SAFE=Number.MAX_SAFE_INTEGER;
function fail(code){{throw new Error(code);}}
function checkedInteger(value){{
 if(typeof value!=='number'||!Number.isSafeInteger(value)) fail('E_A1_UNSAFE_INTEGER');
 return value;
}}
function get(env,x){{
 const value=x&&typeof x==='object'&&Object.keys(x).length===1&&'ref' in x?env[x.ref]:x;
 if(typeof value==='number'&&!Number.isSafeInteger(value)) fail('E_A1_UNSAFE_INTEGER');
 return value;
}}
function checkedText(value,capacity=MAX_SAFE){{
 if(typeof value!=='string') fail('E_A1_TEXT_ENCODING');
 for(let k=0;k<value.length;k++){{
  const code=value.charCodeAt(k);
  if(code===0) fail('E_A1_TEXT_NUL');
  if(code>=0xd800&&code<=0xdbff){{
   if(k+1>=value.length) fail('E_A1_TEXT_ENCODING');
   const next=value.charCodeAt(++k);
   if(next<0xdc00||next>0xdfff) fail('E_A1_TEXT_ENCODING');
  }} else if(code>=0xdc00&&code<=0xdfff) fail('E_A1_TEXT_ENCODING');
 }}
 const bytes=Buffer.byteLength(value,'utf8');
 if(bytes>capacity) fail('E_A1_TEXT_CAPACITY');
 return value;
}}
function textCapacity(type){{return type.capacity===undefined?type.max_bytes:type.capacity;}}
function call(name,args){{
 const f=functions[name]; if(!f) throw new Error('E_A1_CALL');
 const env=Object.fromEntries(f.params.map((p,i)=>[p.name,args[i]]));
 for(const i of f.body){{ let v;
  switch(i.op){{
   case 'const':
    v=i.type&&i.type.kind==='text'?checkedText(i.value,textCapacity(i.type)):i.value;
    if(typeof v==='number') checkedInteger(v);
    break;
   case 'record_make': v={{record:i.record,fields:Object.fromEntries(Object.entries(i.fields).map(([k,x])=>[k,get(env,x)]))}}; break;
   case 'record_get': {{const r=get(env,i.value); if(r.record!==i.record) throw new Error('E_A1_NOMINAL'); v=r.fields[i.field]; break;}}
   case 'variant_make': v={{variant:i.variant,tag:i.tag,value:get(env,i.value)}}; break;
   case 'match_value': {{const x=get(env,i.value); v=get(env,i.arms[x.tag]); break;}}
   case 'list_empty': v={{list:[],capacity:i.capacity}}; break;
   case 'list_append': {{const x=get(env,i.list),item=get(env,i.value); checkedInteger(x.capacity); v=x.list.length>=x.capacity?{{tag:'Err',value:{{tag:'CapacityError'}}}}:{{tag:'Ok',value:{{list:[...x.list,item],capacity:x.capacity}}}}; break;}}
   case 'list_index': {{const x=get(env,i.list),n=get(env,i.index); v=Number.isSafeInteger(n)&&n>=0&&n<x.list.length?{{tag:'Some',value:x.list[n]}}:{{tag:'None',value:null}}; break;}}
   case 'bounded_map': {{const x=get(env,i.list); v={{list:x.list.map(y=>call(i.callback,[y])),capacity:x.capacity}}; break;}}
   case 'bounded_fold': {{const x=get(env,i.list); v=x.list.reduce((a,y)=>call(i.callback,[a,y]),get(env,i.initial)); break;}}
   case 'text_utf8_bytes': {{const text=checkedText(get(env,i.value)); v=Buffer.byteLength(text,'utf8'); break;}}
   case 'text_codepoint_count': {{const text=checkedText(get(env,i.value)); v=Array.from(text).length; break;}}
   case 'text_prefix_codepoints': {{const text=checkedText(get(env,i.value)); const n=checkedInteger(get(env,i.count)); if(n<0) fail('E_A1_REFINEMENT'); v=Array.from(text).slice(0,n).join(''); break;}}
   case 'text_concat': {{const left=checkedText(get(env,i.left)),right=checkedText(get(env,i.right)); checkedInteger(i.capacity); v=checkedText(left+right,i.capacity); break;}}
   case 'refine_nat': v=checkedInteger(get(env,i.value)); if(v<0) throw new Error('E_A1_REFINEMENT'); break;
   case 'add': {{const left=checkedInteger(get(env,i.left)),right=checkedInteger(get(env,i.right)); v=checkedInteger(left+right); break;}}
   case 'call': v=call(i.callee,(i.args||[]).map(x=>get(env,x))); break;
   default: throw new Error('E_A1_OP');
  }} env[i.dest]=v;
 }} return env[f.return];
}}
process.stdout.write(JSON.stringify(call({json.dumps(entry)},initialArgs))+'\\n');
"""
