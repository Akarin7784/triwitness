#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_translator/test_lexer.py::test_data_types_tokenization \
  tests/test_translator/test_lexer.py::test_struct_tokenization \
  tests/test_translator/test_lexer.py::test_if_statement_tokenization \
  tests/test_translator/test_lexer.py::test_for_statement_tokenization \
  tests/test_translator/test_lexer.py::test_else_statement_tokenization \
  tests/test_translator/test_lexer.py::test_else_if_statement_tokenization \
  tests/test_translator/test_lexer.py::test_function_call_tokenization \
  tests/test_translator/test_lexer.py::test_bitwise_operator_tokenization \
  tests/test_translator/test_lexer.py::test_operators_tokenization \
  tests/test_translator/test_lexer.py::test_logical_operators_tokenization \
  tests/test_translator/test_lexer.py::test_assignment_shift_operators \
  tests/test_translator/test_lexer.py::test_assignment_operators_tokenization \
  tests/test_translator/test_lexer.py::test_const_tokenization \
  tests/test_translator/test_lexer.py::test_illegal_character \
  tests/test_translator/test_lexer.py::test_bitwise_not_tokenization; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
