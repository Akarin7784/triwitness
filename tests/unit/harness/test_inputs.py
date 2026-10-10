"""附件 / 用户说明拼进任务描述（UI-21）。"""

from __future__ import annotations

from pathlib import Path

from triwitness.harness.inputs import PER_FILE_CHARS, archive_attachments, compose_task


def test_plain_issue_unchanged() -> None:
    assert compose_task("  修一下  ").prompt == "修一下"


def test_guidance_before_issue_and_attachments_after(tmp_path: Path) -> None:
    a = tmp_path / "notes.md"
    a.write_text("含 ``` 的说明", encoding="utf-8")
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    binf = tmp_path / "blob.bin"
    binf.write_bytes(b"\x00\x01\x02")
    c = compose_task("修 bug", guidance="请用中文写提交信息", attachments=[a, img, binf])
    g, i, att = c.prompt.index("用户设置"), c.prompt.index("修 bug"), c.prompt.index("## 附件")
    assert g < i < att
    assert "````\n含 ``` 的说明\n````" in c.prompt  # 围栏比内容多一个反引号
    assert c.texts == ["notes.md"] and c.images == ["shot.png"] and c.binaries == ["blob.bin"]
    assert "只能读文字" in c.prompt


def test_caps_and_gbk(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_text("x" * (PER_FILE_CHARS + 50), encoding="utf-8")
    gbk = tmp_path / "gbk.txt"
    gbk.write_bytes("中文注释".encode("gb18030"))
    c = compose_task("t", attachments=[big, gbk], guidance="g" * 9000)
    assert c.truncated == ["big.txt"] and "中文注释" in c.prompt and "已截断" in c.prompt


def test_archive(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    a.write_text("1", encoding="utf-8")
    archive_attachments([a], tmp_path / "run")
    assert (tmp_path / "run" / "attachments" / "a.txt").read_text() == "1"
