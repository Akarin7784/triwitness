"""W3-14 结论：model 档只在“确定性 pass 但证据薄”时调用，且只判 1 次。"""

from __future__ import annotations

from triwitness.core.models import TestRun
from triwitness.verify import anticheat
from triwitness.verify.claim import ClaimVerdict
from triwitness.verify.verifier import needs_model, thin_evidence


def run(scope: str, passed: int = 10) -> TestRun:
    return TestRun(scope=scope, command="pytest", passed=passed, failed=0, skipped=0, duration_s=1, log_ref="x")  # type: ignore[arg-type]


EXISTING_TEST_EDIT = """diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1,2 +1,2 @@
 def test_a():
-    assert f() == 1
+    assert f() == 2
"""


def test_well_evidenced_pass_is_not_thin() -> None:
    assert thin_evidence([run("repro_base", 0), run("repro_patched"), run("full")]) == []
    assert not needs_model("pass", [])


def test_thin_signals() -> None:
    assert thin_evidence([run("repro_patched")]) == ["没有回归测试证据"]
    assert thin_evidence([run("related")]) == ["回归只跑了相关测试 + 抽样"]
    ac = anticheat.check(EXISTING_TEST_EDIT)
    assert any(x.startswith("防作弊提示：existing_test_modified") for x in thin_evidence([run("full")], ac))
    claim = ClaimVerdict(verdict="pass", flags=["issue_underspecified"])
    assert thin_evidence([run("full")], claim=claim) == ["声明审计标记：issue_underspecified"]
    # 自报风险单独出现不算薄（W3-14 后续：17/17 个 pass 都自报风险）；有其他信号时作附注
    assert thin_evidence([run("full")], open_risks=["没测负数"]) == []
    assert thin_evidence([run("full")], claim=claim, open_risks=["没测负数"]) == [
        "声明审计标记：issue_underspecified",
        "Executor 自报未覆盖的风险 1 条",
    ]


def test_needs_model_policy() -> None:
    thin = ["没有回归测试证据"]
    assert needs_model("pass", thin)
    assert not needs_model("inconclusive", thin)  # 模型只会更保守，不改变非 pass 的结论
    assert not needs_model("fail", thin)
    assert needs_model("fail", [], "always") and needs_model("pass", [], "always")
