#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  toqito/matrices/tests/test_pauli.py::test_invalid_ind \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[i-expected0]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[I-expected1]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[0-expected2]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[X-expected3]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[x-expected4]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[1-expected5]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[Y-expected6]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[y-expected7]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[2-expected8]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[Z-expected9]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[z-expected10]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_single[3-expected11]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[I]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[0]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[X]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[1]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[Y]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[2]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[Z]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[3]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[i]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[x]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[y]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_sparse[z]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_list[pauli_list0-expected0]' \
  'toqito/matrices/tests/test_pauli.py::test_pauli_list[pauli_list1-expected1]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
