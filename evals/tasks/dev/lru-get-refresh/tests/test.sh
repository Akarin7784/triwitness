#!/usr/bin/env bash
# 判分：把隐藏测试放进仓库 tests/（与 SWE-bench 做法相同），只跑 F2P + P2P；全部通过写 1，否则写 0。
set -u
cd /workspace/repo
mkdir -p /logs/verifier tests
cp /tests/test_lru_hidden.py tests/
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  "tests/test_lru_hidden.py::test_get_refreshes" \
  "tests/test_lru_hidden.py::test_put_get" \
  "tests/test_lru_hidden.py::test_capacity" \
  "tests/test_lru_hidden.py::test_bad_capacity" \
  "tests/test_lru_hidden.py::test_missing_get_does_not_insert"; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
