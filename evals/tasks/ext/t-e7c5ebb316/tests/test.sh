#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_regressions.py::test_issue562_tzcasts \
  tests/test_regressions.py::test_issue9 \
  tests/test_regressions.py::test_issue13 \
  'tests/test_regressions.py::test_issue26[--hello]' \
  'tests/test_regressions.py::test_issue26[--hello\n]' \
  'tests/test_regressions.py::test_issue26[--]' \
  'tests/test_regressions.py::test_issue26[--\n]' \
  'tests/test_regressions.py::test_issue34[create]' \
  'tests/test_regressions.py::test_issue34[CREATE]' \
  tests/test_regressions.py::test_issue35 \
  tests/test_regressions.py::test_issue38 \
  tests/test_regressions.py::test_issue39 \
  tests/test_regressions.py::test_issue40 \
  tests/test_regressions.py::test_issue83 \
  tests/test_regressions.py::test_comment_encoding_when_reindent \
  tests/test_regressions.py::test_parse_sql_with_binary \
  tests/test_regressions.py::test_dont_alias_keywords \
  tests/test_regressions.py::test_format_accepts_encoding \
  tests/test_regressions.py::test_stream \
  tests/test_regressions.py::test_issue90 \
  tests/test_regressions.py::test_except_formatting \
  tests/test_regressions.py::test_null_with_as \
  tests/test_regressions.py::test_issue190_open_file \
  tests/test_regressions.py::test_issue193_splitting_function \
  tests/test_regressions.py::test_issue194_splitting_function \
  tests/test_regressions.py::test_issue186_get_type \
  tests/test_regressions.py::test_issue212_py2unicode \
  tests/test_regressions.py::test_issue213_leadingws \
  tests/test_regressions.py::test_issue227_gettype_cte \
  tests/test_regressions.py::test_issue207_runaway_format \
  tests/test_regressions.py::test_token_next_doesnt_ignore_skip_cm \
  'tests/test_regressions.py::test_issue284_as_grouping[AS]' \
  tests/test_regressions.py::test_issue315_utf8_by_default \
  tests/test_regressions.py::test_issue322_concurrently_is_keyword \
  tests/test_regressions.py::test_issue469_copy_as_psql_command \
  tests/test_regressions.py::test_issue485_split_multi \
  tests/test_regressions.py::test_issue489_tzcasts \
  tests/test_regressions.py::test_as_in_parentheses_indents \
  tests/test_regressions.py::test_format_invalid_where_clause \
  tests/test_regressions.py::test_splitting_at_and_backticks_issue588; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
