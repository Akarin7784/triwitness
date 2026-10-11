#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  zahlwort2num/tests/test_convert.py::TestConverter::test_hardcoded_values_upto_100 \
  zahlwort2num/tests/test_convert.py::TestConverter::test_more_specific \
  zahlwort2num/tests/test_convert.py::TestConverter::test_bugs_found_by_users \
  zahlwort2num/tests/test_convert.py::TestConverter::test_negative_values \
  zahlwort2num/tests/test_convert.py::TestConverter::test_negative_with_ordinal \
  zahlwort2num/tests/test_convert.py::TestConverter::test_ordinal_numbers \
  zahlwort2num/tests/test_convert.py::TestConverter::test_swiss_variant \
  zahlwort2num/tests/test_convert.py::TestConverter::test_yet_another_ordinal_edge_case; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
