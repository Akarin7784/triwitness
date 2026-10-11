#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_autocomplete.py::test_autocomplete_bash_empty \
  'tests/test_autocomplete.py::test_autocomplete_basics[pkg_aa-expected0]' \
  'tests/test_autocomplete.py::test_autocomplete_basics[pkg_aaa-expected1]' \
  'tests/test_autocomplete.py::test_autocomplete_basics[pkg_aaa.-expected2]' \
  'tests/test_autocomplete.py::test_autocomplete_basics[pkg_aaa.m-expected3]' \
  'tests/test_autocomplete.py::test_autocomplete_basics[pkg_aaa.mod_a.-expected4]' \
  'tests/test_autocomplete.py::test_autocomplete_basics[pkg_aaa.mod_a.Test-expected5]' \
  'tests/test_autocomplete.py::test_autocomplete_basics[pkg_aaa.mod_a.Test.-expected6]' \
  'tests/test_autocomplete.py::test_autocomplete_bash[words0-1-expected0]' \
  'tests/test_autocomplete.py::test_autocomplete_bash[words1-1-expected1]' \
  'tests/test_autocomplete.py::test_autocomplete_bash[words2-2-expected2]' \
  'tests/test_autocomplete.py::test_autocomplete_bash[words3-2-expected3]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
