#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_util.py::test_interpolate_intervals_gap \
  tests/test_util.py::test_interpolate_intervals_badtime \
  tests/test_util.py::test_interpolate_intervals \
  tests/test_util.py::test_intervals_to_samples \
  tests/test_util.py::test_intersect_files \
  tests/test_util.py::test_merge_labeled_intervals \
  tests/test_util.py::test_boundaries_to_intervals \
  tests/test_util.py::test_adjust_events \
  tests/test_util.py::test_bipartite_match \
  tests/test_util.py::test_outer_distance_mod_n \
  tests/test_util.py::test_outer_distance \
  tests/test_util.py::test_match_events \
  tests/test_util.py::test_validate_intervals \
  tests/test_util.py::test_validate_events \
  tests/test_util.py::test_validate_frequencies; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
