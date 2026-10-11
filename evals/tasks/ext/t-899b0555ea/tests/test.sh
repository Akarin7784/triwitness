#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_doccmd.py::test_command_not_found \
  tests/test_doccmd.py::test_not_executable \
  tests/test_doccmd.py::test_help \
  tests/test_doccmd.py::test_run_command \
  tests/test_doccmd.py::test_file_does_not_exist \
  tests/test_doccmd.py::test_multiple_code_blocks \
  tests/test_doccmd.py::test_language_filters \
  tests/test_doccmd.py::test_run_command_no_pad_file \
  tests/test_doccmd.py::test_multiple_files \
  tests/test_doccmd.py::test_multiple_files_multiple_types \
  tests/test_doccmd.py::test_modify_file \
  tests/test_doccmd.py::test_exit_code \
  'tests/test_doccmd.py::test_file_extension[python-.py]' \
  'tests/test_doccmd.py::test_file_extension[javascript-.js]' \
  'tests/test_doccmd.py::test_given_file_extension[foobar]' \
  'tests/test_doccmd.py::test_given_file_extension[.foobar]' \
  tests/test_doccmd.py::test_given_prefix \
  tests/test_doccmd.py::test_file_extension_unknown_language \
  tests/test_doccmd.py::test_file_given_multiple_times \
  tests/test_doccmd.py::test_verbose \
  tests/test_doccmd.py::test_directory_passed_in \
  tests/test_doccmd.py::test_main_entry_point; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
