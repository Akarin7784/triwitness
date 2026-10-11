#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/strategies/ecospold2.py::test_add_cpc_classification_from_single_reference_product_single_classif \
  tests/strategies/ecospold2.py::test_drop_temporary_outdated_biosphere_flows \
  tests/strategies/ecospold2.py::test_reparametrize_lognormal_to_agree_with_static_amount \
  tests/strategies/ecospold2.py::test_fix_unreasonably_high_lognormal_uncertainties \
  tests/strategies/ecospold2.py::test_remove_uncertainty_from_negative_loss_exchanges \
  tests/strategies/ecospold2.py::test_delete_none_synonyms \
  tests/strategies/ecospold2.py::test_add_cpc_classification_from_single_reference_product \
  tests/strategies/ecospold2.py::test_set_lognormal_loc_value; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
