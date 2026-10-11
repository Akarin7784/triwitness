#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  diff_cover/tests/test_diff_cover_tool.py::test_parse_with_multiple_reports \
  diff_cover/tests/test_diff_cover_tool.py::test_parse_with_html_report \
  diff_cover/tests/test_diff_cover_tool.py::test_parse_with_no_report \
  diff_cover/tests/test_diff_cover_tool.py::test_parse_with_ignored_unstaged \
  diff_cover/tests/test_diff_cover_tool.py::test_parse_invalid_arg \
  diff_cover/tests/test_diff_cover_tool.py::test_parse_with_exclude; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
