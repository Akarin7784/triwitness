#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  pycytominer/tests/test_cyto_utils/test_feature_drop_outlier.py::test_outlier_default \
  pycytominer/tests/test_feature_select.py::test_feature_select_drop_outlier \
  pycytominer/tests/test_cyto_utils/test_feature_drop_outlier.py::test_outlier_15_cutoff \
  pycytominer/tests/test_cyto_utils/test_feature_drop_outlier.py::test_outlier_samples_15 \
  pycytominer/tests/test_cyto_utils/test_feature_drop_outlier.py::test_outlier_features \
  pycytominer/tests/test_feature_select.py::test_feature_select_noise_removal \
  pycytominer/tests/test_feature_select.py::test_feature_select_get_na_columns \
  pycytominer/tests/test_feature_select.py::test_feature_select_get_na_columns_feature_infer \
  pycytominer/tests/test_feature_select.py::test_feature_select_variance_threshold \
  pycytominer/tests/test_feature_select.py::test_feature_select_correlation_threshold \
  pycytominer/tests/test_feature_select.py::test_feature_select_all \
  pycytominer/tests/test_feature_select.py::test_feature_select_compress \
  pycytominer/tests/test_feature_select.py::test_feature_select_blocklist; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
