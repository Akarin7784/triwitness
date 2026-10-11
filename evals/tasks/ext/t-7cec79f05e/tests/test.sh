#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/test_pdo.py::TestPDO::test_pdo_getitem \
  test/test_pdo.py::TestPDO::test_pdo_iterate \
  test/test_pdo.py::TestPDO::test_pdo_export \
  test/test_pdo.py::TestPDO::test_pdo_map_bit_mapping \
  test/test_pdo.py::TestPDO::test_pdo_map_getitem \
  test/test_pdo.py::TestPDO::test_pdo_maps_iterate \
  test/test_pdo.py::TestPDO::test_pdo_save \
  test/test_pdo.py::TestPDO::test_pdo_save_skip_readonly; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
