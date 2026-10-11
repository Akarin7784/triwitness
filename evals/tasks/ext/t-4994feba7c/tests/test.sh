#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/reg_tests/jensen_jimenez_regression_test.py::test_regression_small_grid_rotation \
  tests/reg_tests/gauss_regression_test.py::test_regression_tandem \
  tests/reg_tests/gauss_regression_test.py::test_regression_rotation \
  tests/reg_tests/gauss_regression_test.py::test_regression_yaw \
  tests/reg_tests/gauss_regression_test.py::test_regression_gch \
  tests/reg_tests/gauss_regression_test.py::test_regression_yaw_added_recovery \
  tests/reg_tests/gauss_regression_test.py::test_regression_secondary_steering \
  tests/reg_tests/gauss_regression_test.py::test_regression_small_grid_rotation \
  tests/reg_tests/jensen_jimenez_regression_test.py::test_regression_tandem \
  tests/reg_tests/jensen_jimenez_regression_test.py::test_regression_rotation \
  tests/reg_tests/jensen_jimenez_regression_test.py::test_regression_yaw; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
