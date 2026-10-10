#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'test/test_cli.py::test_cli_help[command_path6]' \
  'test/test_cli.py::test_cli_help[command_path7]' \
  'test/test_cli.py::test_cli_add_file[False]' \
  'test/test_cli.py::test_cli_add_file[True]' \
  'test/test_cli.py::test_cli_add_dataset[False]' \
  'test/test_cli.py::test_cli_add_dataset[True]' \
  'test/test_cli.py::test_cli_help[command_path0]' \
  'test/test_cli.py::test_cli_help[command_path1]' \
  'test/test_cli.py::test_cli_help[command_path2]' \
  'test/test_cli.py::test_cli_help[command_path3]' \
  'test/test_cli.py::test_cli_help[command_path4]' \
  'test/test_cli.py::test_cli_help[command_path5]' \
  'test/test_cli.py::test_cli_init[False-False]' \
  'test/test_cli.py::test_cli_init[False-True]' \
  'test/test_cli.py::test_cli_init[True-False]' \
  'test/test_cli.py::test_cli_init[True-True]' \
  test/test_cli.py::test_cli_init_exclude \
  'test/test_cli.py::test_cli_add_workflow[False]' \
  'test/test_cli.py::test_cli_add_workflow[True]' \
  'test/test_cli.py::test_cli_add_test_metadata[False]' \
  'test/test_cli.py::test_cli_add_test_metadata[True]' \
  'test/test_cli.py::test_cli_add_test_metadata_explicit_ids[False]' \
  'test/test_cli.py::test_cli_add_test_metadata_explicit_ids[True]' \
  'test/test_cli.py::test_cli_write_zip[False]' \
  'test/test_cli.py::test_cli_write_zip[True]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
