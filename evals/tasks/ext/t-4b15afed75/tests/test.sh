#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_fuzzyfinder.py::test_case_sensitive_substring_match \
  tests/test_fuzzyfinder.py::test_substring_match \
  tests/test_fuzzyfinder.py::test_case_insensitive_substring_match \
  tests/test_fuzzyfinder.py::test_use_shortest_match_if_matches_overlap \
  tests/test_fuzzyfinder.py::test_substring_match_with_dot \
  tests/test_fuzzyfinder.py::test_fuzzy_match \
  tests/test_fuzzyfinder.py::test_fuzzy_match_ranking \
  tests/test_fuzzyfinder.py::test_fuzzy_match_greedy \
  tests/test_fuzzyfinder.py::test_fuzzy_integer_input \
  tests/test_fuzzyfinder.py::test_accessor \
  tests/test_fuzzyfinder.py::test_no_alpha_num_sort; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
