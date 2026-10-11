#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructuralHammingDistance::test_shd_isolated_nodes \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructuralHammingDistance::test_shd_mixed_differences \
  pgmpy/tests/test_metrics/test_metrics.py::TestCorrelationScore::test_discrete_network \
  pgmpy/tests/test_metrics/test_metrics.py::TestCorrelationScore::test_input \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructureScore::test_discrete_network \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructureScore::test_input \
  pgmpy/tests/test_metrics/test_metrics.py::TestLogLikelihoodScore::test_discrete_network \
  pgmpy/tests/test_metrics/test_metrics.py::TestLogLikelihoodScore::test_input \
  pgmpy/tests/test_metrics/test_metrics.py::TestImpliedCI::test_fisher_c \
  pgmpy/tests/test_metrics/test_metrics.py::TestImpliedCI::test_implied_cis \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructuralHammingDistance::test_shd1 \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructuralHammingDistance::test_shd2 \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructuralHammingDistance::test_shd3 \
  pgmpy/tests/test_metrics/test_metrics.py::TestStructuralHammingDistance::test_shd_unequal_graphs; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
