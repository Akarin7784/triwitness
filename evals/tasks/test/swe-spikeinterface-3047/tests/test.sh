#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  src/spikeinterface/core/tests/test_sortinganalyzer.py::test_SortingAnalyzer_binary_folder \
  src/spikeinterface/core/tests/test_sortinganalyzer.py::test_SortingAnalyzer_memory \
  src/spikeinterface/core/tests/test_sortinganalyzer.py::test_SortingAnalyzer_zarr \
  src/spikeinterface/core/tests/test_sortinganalyzer.py::test_SortingAnalyzer_tmp_recording \
  src/spikeinterface/core/tests/test_sortinganalyzer.py::test_extension_params \
  src/spikeinterface/core/tests/test_sortinganalyzer.py::test_extension \
  src/spikeinterface/core/tests/test_sortinganalyzer.py::test_extensions_sorting; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
