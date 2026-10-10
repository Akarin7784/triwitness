#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_add_option_format.py::test_invalid_format_key_emits_helpful_error_with_catch \
  tests/test_add_option_format.py::test_invalid_format_key_error_message_content \
  'tests/test_add_option_format.py::test_format[b-Nope-Nope\n]' \
  'tests/test_add_option_format.py::test_format[e-<lambda>-e]' \
  tests/test_add_option_format.py::test_progressive_format \
  tests/test_add_option_format.py::test_function_format_without_exception \
  tests/test_add_option_format.py::test_function_format_with_exception \
  'tests/test_add_option_format.py::test_invalid_format[-1]' \
  'tests/test_add_option_format.py::test_invalid_format[3.4]' \
  'tests/test_add_option_format.py::test_invalid_format[format2]' \
  'tests/test_add_option_format.py::test_invalid_markups[<red>]' \
  'tests/test_add_option_format.py::test_invalid_markups[</red>]' \
  'tests/test_add_option_format.py::test_invalid_markups[</level><level>]' \
  'tests/test_add_option_format.py::test_invalid_markups[</>]' \
  'tests/test_add_option_format.py::test_invalid_markups[<foobar>]' \
  'tests/test_add_option_format.py::test_markup_in_field[True]' \
  'tests/test_add_option_format.py::test_markup_in_field[False]' \
  tests/test_add_option_format.py::test_invalid_format_builtin \
  tests/test_add_option_format.py::test_invalid_format_key_raises_enhanced_error_without_catch \
  tests/test_add_option_format.py::test_patcher_added_keys_work_in_format; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
