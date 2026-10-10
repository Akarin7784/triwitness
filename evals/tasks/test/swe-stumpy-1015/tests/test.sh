#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_motifs.py::test_motifs_with_max_matches_none \
  tests/test_motifs.py::test_motifs_one_motif \
  tests/test_motifs.py::test_motifs_two_motifs \
  tests/test_motifs.py::test_motifs_max_matches \
  tests/test_motifs.py::test_motifs_max_matches_max_distances_inf \
  tests/test_motifs.py::test_naive_match_exclusion_zone \
  'tests/test_motifs.py::test_match[Q0-T0]' \
  'tests/test_motifs.py::test_match[Q1-T1]' \
  'tests/test_motifs.py::test_match[Q2-T2]' \
  'tests/test_motifs.py::test_match_mean_stddev[Q0-T0]' \
  'tests/test_motifs.py::test_match_mean_stddev[Q1-T1]' \
  'tests/test_motifs.py::test_match_mean_stddev[Q2-T2]' \
  'tests/test_motifs.py::test_match_isconstant[Q0-T0]' \
  'tests/test_motifs.py::test_match_isconstant[Q1-T1]' \
  'tests/test_motifs.py::test_match_isconstant[Q2-T2]' \
  'tests/test_motifs.py::test_match_mean_stddev_isconstant[Q0-T0]' \
  'tests/test_motifs.py::test_match_mean_stddev_isconstant[Q1-T1]' \
  'tests/test_motifs.py::test_match_mean_stddev_isconstant[Q2-T2]' \
  tests/test_motifs.py::test_multi_match \
  tests/test_motifs.py::test_multi_match_isconstant \
  tests/test_motifs.py::test_motifs \
  tests/test_motifs.py::test_motifs_with_isconstant; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
