#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'stonesoup/types/tests/test_angle.py::test_misc[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_misc[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_hash[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_hash[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_bearing_init[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_bearing_init[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_bearing_init[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_bearing_init[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_multiply[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_multiply[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_multiply[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_multiply[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_addition[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_addition[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_addition[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_addition[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_subtraction[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_subtraction[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_subtraction[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_subtraction[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_division[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_division[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_division[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_division[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_comparison[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_comparison[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_comparison[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_comparison[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_trig[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_trig[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_trig[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_trig[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_misc[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_misc[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_degrees[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_degrees[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_degrees[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_degrees[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_average[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_average[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_wrapping_equality_and_abs[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_wrapping_equality_and_abs[Elevation]' \
  'stonesoup/types/tests/test_angle.py::test_wrapping_equality_and_abs[Longitude]' \
  'stonesoup/types/tests/test_angle.py::test_wrapping_equality_and_abs[Latitude]' \
  'stonesoup/types/tests/test_angle.py::test_hash[Bearing]' \
  'stonesoup/types/tests/test_angle.py::test_hash[Longitude]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
