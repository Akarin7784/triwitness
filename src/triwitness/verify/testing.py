"""测试用的小 diff 构造器（单测与 fixture 共用，和 harness.testing 一样放在包里）。"""

from __future__ import annotations


def modify(path: str, removed: list[str], added: list[str], start: int = 1) -> str:
    body = [f"-{r}" for r in removed] + [f"+{a}" for a in added]
    return (f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -{start},{len(removed)} +{start},{len(added)} @@\n" + "\n".join(body) + "\n")  # fmt: skip


def new_file(path: str, lines: list[str]) -> str:
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..3333333\n--- /dev/null\n"
            f"+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + "\n".join(f"+{x}" for x in lines) + "\n")  # fmt: skip


def delete(path: str, lines: list[str]) -> str:
    return (f"diff --git a/{path} b/{path}\ndeleted file mode 100644\nindex 3333333..0000000\n--- a/{path}\n"
            f"+++ /dev/null\n@@ -1,{len(lines)} +0,0 @@\n" + "\n".join(f"-{x}" for x in lines) + "\n")  # fmt: skip
