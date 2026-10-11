#!/usr/bin/env python3
"""
标题衬线体子集（perf）：Noto Serif SC 只用于标题 / 会话名 / Markdown 标题（短文本），
把 fontsource 的每个 unicode-range 切片裁到 GB2312（6763 字）+ ASCII/拉丁-1 + 常用标点，
切片结构不变（仍按需加载），unicode-range 同步收窄——集外字直接回退到正文的 Noto Sans SC（全量覆盖）。
正文 Noto Sans SC 不裁：agent 输出的字不可控，正文必须全覆盖。

用法（需要 fonttools + brotli）：python3 scripts/subset-serif.py
产物：src/assets/fonts/serif/*.woff2 + src/assets/fonts/noto-serif-sc-subset.css（提交进仓库，构建时不依赖 Python）
"""
import os
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'node_modules/@fontsource/noto-serif-sc'
OUT = ROOT / 'src/assets/fonts/serif'
CSS = ROOT / 'src/assets/fonts/noto-serif-sc-subset.css'
WEIGHTS = ['500', '600']


def gb2312() -> set[int]:
    out = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                out.add(ord(bytes([hi, lo]).decode('gb2312')))
            except UnicodeDecodeError:
                pass
    return out


KEEP = gb2312() | set(range(0x20, 0x7F)) | set(range(0xA0, 0x100)) | set(range(0x2000, 0x2070)) \
    | set(range(0x3000, 0x3040)) | set(range(0xFF00, 0xFFF0))


def parse_range(s: str) -> set[int]:
    cps = set()
    for part in s.split(','):
        part = part.strip().upper().replace('U+', '')
        if '-' in part:
            a, b = part.split('-')
            cps.update(range(int(a, 16), int(b, 16) + 1))
        elif part:
            cps.add(int(part, 16))
    return cps


def fmt_range(cps: set[int]) -> str:
    xs = sorted(cps)
    out, i = [], 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        out.append(f'U+{xs[i]:x}' if i == j else f'U+{xs[i]:x}-{xs[j]:x}')
        i = j + 1
    return ', '.join(out)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob('*.woff2'):
        f.unlink()
    css_out = ['/* 生成文件：scripts/subset-serif.py —— Noto Serif SC（SIL OFL 1.1）按 GB2312 裁剪的切片 */']
    before = after = 0
    for w in WEIGHTS:
        css = (SRC / f'{w}.css').read_text()
        for face in re.findall(r'@font-face\s*\{(.*?)\}', css, re.S):
            name = re.search(r'([\w-]+-normal\.woff2)', face).group(1)
            if re.search(r'-(cyrillic|vietnamese|greek)', name):
                continue
            cps = parse_range(re.search(r'unicode-range:\s*([^;]+);', face).group(1))
            src = SRC / 'files' / name
            before += src.stat().st_size
            font = TTFont(src)
            have = set(font.getBestCmap().keys())
            keep = cps & KEEP & have
            if not keep:
                continue
            opts = subset.Options()
            opts.flavor = 'woff2'
            opts.layout_features = ['*']
            opts.name_IDs = ['*']
            opts.notdef_outline = True
            sub = subset.Subsetter(options=opts)
            sub.populate(unicodes=keep)
            sub.subset(font)
            dst = OUT / name
            font.flavor = 'woff2'
            font.save(dst)
            after += dst.stat().st_size
            css_out.append(
                '@font-face {\n'
                "  font-family: 'Noto Serif SC';\n  font-style: normal;\n  font-display: swap;\n"
                f'  font-weight: {w};\n  src: url(./serif/{name}) format(\'woff2\');\n'
                f'  unicode-range: {fmt_range(keep)};\n}}'
            )
    CSS.write_text('\n'.join(css_out) + '\n')
    print(f'serif: {before / 1024:.0f} KB -> {after / 1024:.0f} KB, {len(css_out) - 1} faces')
    return 0


if __name__ == '__main__':
    sys.exit(main())
