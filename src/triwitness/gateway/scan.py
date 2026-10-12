"""注入特征扫描（spec 014 §5.3、§7）：MCP 工具描述 / 返回内容、跨 agent 委托消息共用。

复用记忆静态检查的 bypass / exfiltration / secret 规则（spec 013 §6），再加工具投毒常见特征：
隐藏指令标签、敏感路径、管道执行、不可见字符（零宽、Unicode tag 字符）、长 base64 块、冒充授权。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EXTRA = [
    (r"(?i)<\s*(important|system|instructions?|admin)\s*>", "隐藏指令标签"),
    (
        r"(?i)(~|\$HOME|/root|/home/\w+)/\.(ssh|aws|config/gcloud|docker|kube|netrc|npmrc|pypirc)\b|id_rsa|id_ed25519",
        "敏感凭据路径",
    ),
    (r"(?i)(^|[\s/])\.env\b|/proc/self/environ|\bprintenv\b|\benv\s*\|", "读取环境变量 / .env"),
    (r"(?i)\b(curl|wget)\b[^\n|]*\|\s*(ba|z)?sh\b", "下载后管道执行"),
    (r"(?i)\b(do\s+not|don'?t|never)\s+(tell|inform|mention|show)\s+(the\s+)?user", "要求对用户隐瞒"),
    (r"(不要|别|切勿)(告诉|通知|提醒)用户", "要求对用户隐瞒"),
    (
        r"(?i)\b(the\s+)?user\s+(has\s+)?(already\s+)?(pre-?)?approved\b|\bapproved\s+by\s+(the\s+)?(user|admin|eva)\b",
        "冒充授权",
    ),
    (r"(用户|管理员)(已经|已)?(提前)?(批准|授权|同意)", "冒充授权"),
    (r"(?i)\b(before|instead\s+of)\s+(using|calling)\s+(any\s+)?(other\s+)?tools?\b", "劫持其他工具"),
    (r"(?i)\bforce[- ]?push\b|push\s+(--force|-f)\b|git\s+push\s+\S*\s*\+", "强推"),
    (
        r"(?i)\b(print|echo|cat|show|dump|leak|exfiltrate)\b[^\n]{0,40}\b"
        r"(API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|DEEPSEEK_|OPENAI_|GITHUB_TOKEN)\b",
        "要求打印密钥",
    ),
    (r"(把|打印|输出|贴出)[^。\n]{0,20}(API[_-]?KEY|TOKEN|密钥|令牌|密码|凭据)", "要求打印密钥"),
]
_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]|[\U000e0000-\U000e007f]")
_B64 = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")


@dataclass(frozen=True)
class Hit:
    rule: str
    why: str


def scan(text: str) -> list[Hit]:
    from triwitness.memory.checks import check_bypass, check_exfiltration, check_secret

    hits = [Hit(f.rule, f.detail) for f in check_bypass(text) + check_exfiltration(text) + check_secret(text)]
    seen = {h.why for h in hits}
    for pat, why in _EXTRA:
        if why not in seen and re.search(pat, text, flags=re.MULTILINE):
            hits.append(Hit("injection", why))
            seen.add(why)
    if _INVISIBLE.search(text):
        hits.append(Hit("injection", "不可见字符"))
    if _B64.search(text):
        hits.append(Hit("injection", "长 base64 块"))
    return hits


__all__ = ["Hit", "scan"]
