#!/usr/bin/env bash
# 判分：把隐藏测试放进仓库 tests/（与 SWE-bench 做法相同），只跑 F2P + P2P；全部通过写 1，否则写 0。
set -u
cd /workspace/repo
mkdir -p /logs/verifier tests
cp /tests/test_pager_hidden.py tests/
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  "tests/test_pager_hidden.py::test_partial_last_page" \
  "tests/test_pager_hidden.py::test_full_pages" \
  "tests/test_pager_hidden.py::test_empty" \
  "tests/test_pager_hidden.py::test_out_of_range"; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
