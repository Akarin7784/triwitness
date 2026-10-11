#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  mpmath/tests/test_functions2.py::test_issue_991 \
  mpmath/tests/test_functions2.py::test_bessel \
  mpmath/tests/test_functions2.py::test_issue_877 \
  mpmath/tests/test_functions2.py::test_bessel_zeros \
  mpmath/tests/test_functions2.py::test_hankel \
  mpmath/tests/test_functions2.py::test_struve \
  mpmath/tests/test_functions2.py::test_whittaker \
  mpmath/tests/test_functions2.py::test_kelvin \
  mpmath/tests/test_functions2.py::test_hyper_misc \
  mpmath/tests/test_functions2.py::test_elliptic_integrals \
  mpmath/tests/test_functions2.py::test_exp_integrals \
  mpmath/tests/test_functions2.py::test_ei \
  mpmath/tests/test_functions2.py::test_e1 \
  mpmath/tests/test_functions2.py::test_expint \
  mpmath/tests/test_functions2.py::test_trig_integrals \
  mpmath/tests/test_functions2.py::test_airy \
  mpmath/tests/test_functions2.py::test_hyper_0f1 \
  mpmath/tests/test_functions2.py::test_hyper_1f1 \
  mpmath/tests/test_functions2.py::test_hyper_2f1 \
  mpmath/tests/test_functions2.py::test_hyper_2f1_hard \
  mpmath/tests/test_functions2.py::test_hyper_3f2_etc \
  mpmath/tests/test_functions2.py::test_hyper_u \
  mpmath/tests/test_functions2.py::test_hyper_2f0 \
  mpmath/tests/test_functions2.py::test_hyper_1f2 \
  mpmath/tests/test_functions2.py::test_hyper_2f3 \
  mpmath/tests/test_functions2.py::test_hyper_2f2 \
  mpmath/tests/test_functions2.py::test_orthpoly \
  mpmath/tests/test_functions2.py::test_hermite \
  mpmath/tests/test_functions2.py::test_gegenbauer \
  mpmath/tests/test_functions2.py::test_legenp \
  mpmath/tests/test_functions2.py::test_legenq \
  mpmath/tests/test_functions2.py::test_agm \
  mpmath/tests/test_functions2.py::test_gammainc \
  mpmath/tests/test_functions2.py::test_gammainc_expint_n \
  mpmath/tests/test_functions2.py::test_incomplete_beta \
  mpmath/tests/test_functions2.py::test_erf \
  mpmath/tests/test_functions2.py::test_pdf \
  mpmath/tests/test_functions2.py::test_lambertw \
  mpmath/tests/test_functions2.py::test_lambertw_hard \
  mpmath/tests/test_functions2.py::test_meijerg \
  mpmath/tests/test_functions2.py::test_foxh \
  mpmath/tests/test_functions2.py::test_appellf1 \
  mpmath/tests/test_functions2.py::test_coulomb \
  mpmath/tests/test_functions2.py::test_hyper_param_accuracy \
  mpmath/tests/test_functions2.py::test_hypercomb_zero_pow \
  mpmath/tests/test_functions2.py::test_spherharm \
  mpmath/tests/test_functions2.py::test_qfunctions \
  mpmath/tests/test_functions2.py::test_issue_239 \
  mpmath/tests/test_functions2.py::test_bessel_zeros_extra \
  mpmath/tests/test_functions2.py::test_issue_569 \
  mpmath/tests/test_functions2.py::test_issue_523 \
  mpmath/tests/test_functions2.py::test_issue_512 \
  mpmath/tests/test_functions2.py::test_issue_251 \
  mpmath/tests/test_functions2.py::test_issue_505 \
  mpmath/tests/test_functions2.py::test_issue_653 \
  mpmath/tests/test_functions2.py::test_issue_511 \
  mpmath/tests/test_functions2.py::test_issue_473 \
  mpmath/tests/test_functions2.py::test_issue_634 \
  mpmath/tests/test_functions2.py::test_issue_908 \
  mpmath/tests/test_functions2.py::test_issue_637; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
