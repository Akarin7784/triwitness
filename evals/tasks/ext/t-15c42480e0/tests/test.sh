#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/sfcf_in_test.py::test_get_rep_name \
  tests/sfcf_in_test.py::test_get_appended_rep_name \
  tests/sfcf_in_test.py::test_o_bb \
  tests/sfcf_in_test.py::test_o_bi \
  tests/sfcf_in_test.py::test_o_bi_files \
  tests/sfcf_in_test.py::test_o_bib \
  tests/sfcf_in_test.py::test_simple_multi_o \
  tests/sfcf_in_test.py::test_dict_multi_o \
  tests/sfcf_in_test.py::test_c_bb \
  tests/sfcf_in_test.py::test_c_bi \
  tests/sfcf_in_test.py::test_c_bi_files \
  tests/sfcf_in_test.py::test_c_bi_files_int_fail \
  tests/sfcf_in_test.py::test_c_bib \
  tests/sfcf_in_test.py::test_simple_multi_c \
  tests/sfcf_in_test.py::test_dict_multi_c \
  tests/sfcf_in_test.py::test_dict_multi_wf_c \
  tests/sfcf_in_test.py::test_a_bb \
  tests/sfcf_in_test.py::test_a_bi \
  tests/sfcf_in_test.py::test_a_bi_files \
  tests/sfcf_in_test.py::test_a_bi_files_int_fail \
  tests/sfcf_in_test.py::test_a_bib \
  tests/sfcf_in_test.py::test_simple_multi_a \
  tests/sfcf_in_test.py::test_dict_multi_a \
  tests/sfcf_in_test.py::test_find_corr \
  tests/sfcf_in_test.py::test_read_compact_file \
  tests/sfcf_in_test.py::test_find_correlator; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
