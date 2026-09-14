# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, os.path.abspath("api"))
import model_router as mr

# 1) strict schema 补 additionalProperties
tools = [
    {"type": "function", "function": {"name": "f", "strict": True,
     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "p"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "g", "strict": False,
     "parameters": {"type": "object", "properties": {"a": {"type": "string"}}}}},
]
out = mr._normalize_tools_for_upstream(tools)
assert out[0]["function"]["parameters"]["additionalProperties"] is False, out
assert out[1]["function"]["parameters"].get("additionalProperties") is None
# 嵌套 object 也补
tools2 = [{"type": "function", "function": {"name": "h", "strict": True,
    "parameters": {"type": "object", "properties": {"nested": {"type": "object", "properties": {"x": {"type": "string"}}}}, "required": ["nested"]}}}]
out2 = mr._normalize_tools_for_upstream(tools2)
assert out2[0]["function"]["parameters"]["properties"]["nested"]["additionalProperties"] is False, out2
# 扁平 Responses 形状也转换
flat = [{"type": "function", "name": "shell", "description": "d", "strict": True,
         "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
out3 = mr._normalize_tools_for_upstream(flat)
assert out3[0]["function"]["name"] == "shell" and out3[0]["function"]["parameters"]["additionalProperties"] is False, out3
print("1) strict schema OK")

# 2) 错误分类
class R:
    status_code = 400
    text = '{"error":{"message":"Invalid schema"}}'
class E(Exception):
    def __init__(self, r=None):
        self.response = r
        super().__init__("client error")
kind, detail = mr._upstream_error_class(E(R()))
assert kind == "format" and "Invalid schema" in detail, (kind, detail)
class R5:
    status_code = 502
    text = "bad gateway"
kind2, _ = mr._upstream_error_class(E(R5()))
assert kind2 == "server", kind2
class R403:
    status_code = 403
    text = "not available in your region"
kind3, d3 = mr._upstream_error_class(E(R403()))
assert kind3 == "auth", kind3
kind4, _ = mr._upstream_error_class(TimeoutError("timeout"))
assert kind4 == "network", kind4
print("2) error class OK")

# 3) invoke 解析
xml = 'I will call the tool.\n<invoke name="read_file">\n<parameter name="path">/etc/hosts</parameter>\n</invoke>\nDone.'
tcs = mr._parse_invoke_tool_calls(xml)
assert tcs and tcs[0]["function"]["name"] == "read_file", tcs
assert json.loads(tcs[0]["function"]["arguments"]) == {"path": "/etc/hosts"}, tcs
tcs2 = mr._parse_invoke_tool_calls("collab:bash")
assert tcs2 and tcs2[0]["function"]["name"] == "bash", tcs2
tcs3 = mr._parse_invoke_tool_calls("normal prose without tools")
assert tcs3 is None, tcs3
print("3) invoke parse OK")

# 4) anthropic 判定
assert mr._is_anthropic_upstream("claude-sonnet-5", "openrouter") is True
assert mr._is_anthropic_upstream("gpt-5.6-luna", "tokenlab") is False
print("4) anthropic detect OK")
