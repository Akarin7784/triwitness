#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/unit/test_snow2.py::Snow2Test::test_parse_pad_width_2d \
  test/unit/test_snow2.py::Snow2Test::test_parse_pad_width_3d \
  test/unit/test_snow2.py::Snow2Test::test_single_phase_2d_serial \
  test/unit/test_snow2.py::Snow2Test::test_return_all_serial \
  test/unit/test_snow2.py::Snow2Test::test_multiphase_2d \
  test/unit/test_snow2.py::Snow2Test::test_single_phase_3d \
  test/unit/test_snow2.py::Snow2Test::test_multiphase_3d \
  test/unit/test_snow2.py::Snow2Test::test_label_phases \
  test/unit/test_snow2.py::Snow2Test::test_ensure_correct_sizes_are_returned_single_phase_2d \
  test/unit/test_snow2.py::Snow2Test::test_ensure_correct_sizes_are_returned_dual_phase_2d \
  test/unit/test_snow2.py::Snow2Test::test_ensure_correct_sizes_are_returned_single_phase_3d \
  test/unit/test_snow2.py::Snow2Test::test_ensure_correct_sizes_are_returned_dual_phase_3d \
  test/unit/test_snow2.py::Snow2Test::test_trim_saddle_points \
  test/unit/test_snow2.py::Snow2Test::test_trim_saddle_points_legacy \
  test/unit/test_snow2.py::Snow2Test::test_accuracy_standard \
  test/unit/test_snow2.py::Snow2Test::test_single_and_dual_phase_on_blobs \
  test/unit/test_snow2.py::Snow2Test::test_send_peaks_to_snow_partitioning \
  test/unit/test_snow2.py::Snow2Test::test_send_peaks_to_snow_partitioning_n \
  test/unit/test_snow2.py::Snow2Test::test_snow2_with_peaks \
  test/unit/test_snow2.py::Snow2Test::test_two_phases_and_boundary_nodes; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
