#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_arhenius_property.py::test_value_returns_pint_quantity \
  'tests/test_arhenius_property.py::test_fit[data_T0-data_y0]' \
  'tests/test_arhenius_property.py::test_fit[data_T1-data_y1]' \
  'tests/test_arhenius_property.py::test_fit[data_T2-data_y2]' \
  'tests/test_arhenius_property.py::test_fit[data_T3-data_y3]' \
  'tests/test_arhenius_property.py::test_fit[data_T4-data_y4]' \
  'tests/test_arhenius_property.py::test_fit[data_T5-data_y5]' \
  'tests/test_arhenius_property.py::test_fit[data_T6-data_y6]' \
  'tests/test_arhenius_property.py::test_fit[data_T7-data_y7]' \
  'tests/test_arhenius_property.py::test_fit[data_T8-data_y8]' \
  'tests/test_arhenius_property.py::test_fit[data_T9-data_y9]' \
  'tests/test_arhenius_property.py::test_fit[data_T10-data_y10]' \
  'tests/test_arhenius_property.py::test_fit[data_T11-data_y11]' \
  'tests/test_arhenius_property.py::test_fit[data_T12-data_y12]' \
  'tests/test_arhenius_property.py::test_fit[data_T13-data_y13]' \
  'tests/test_arhenius_property.py::test_fit[data_T14-data_y14]' \
  'tests/test_arhenius_property.py::test_fit[data_T15-data_y15]' \
  tests/test_arhenius_property.py::test_pre_exp_getter_fit \
  tests/test_arhenius_property.py::test_act_energy_getter_fit \
  'tests/test_arhenius_property.py::test_value[300-3-0.2]' \
  'tests/test_arhenius_property.py::test_value[205-6-0.8]' \
  'tests/test_arhenius_property.py::test_value[600-100000.0-1.2]' \
  tests/test_arhenius_property.py::test_fit_creates_temp_range \
  'tests/test_arhenius_property.py::test_data_T_removes_nan[data0]' \
  'tests/test_arhenius_property.py::test_data_T_removes_nan[data1]' \
  'tests/test_arhenius_property.py::test_data_y_removes_nan[data0]' \
  'tests/test_arhenius_property.py::test_data_y_removes_nan[data1]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
