#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_inheritance_invariant.py::TestOK::test_level_1_inheritance_of_invariants_does_not_leak_to_parents \
  tests/test_inheritance_invariant.py::TestOK::test_level_2_inheritance_of_invariants_does_not_leak_to_parents \
  tests/test_inheritance_invariant.py::TestOK::test_level_3_inheritance_of_invariants_does_not_leak_to_parents \
  tests/test_inheritance_invariant.py::TestOK::test_count_checks \
  tests/test_inheritance_invariant.py::TestViolation::test_additional_invariant_violated_in_childs_init \
  tests/test_inheritance_invariant.py::TestViolation::test_inherited \
  tests/test_inheritance_invariant.py::TestViolation::test_inherited_violated_in_child \
  tests/test_inheritance_invariant.py::TestViolation::test_method_violates_in_child \
  tests/test_inheritance_invariant.py::TestViolation::test_triple_inheritance \
  tests/test_inheritance_invariant.py::TestViolation::test_with_abstract_method \
  tests/test_inheritance_invariant.py::TestProperty::test_inherited_deleter \
  tests/test_inheritance_invariant.py::TestProperty::test_inherited_getter \
  tests/test_inheritance_invariant.py::TestProperty::test_inherited_invariant_on_deleter \
  tests/test_inheritance_invariant.py::TestProperty::test_inherited_invariant_on_getter \
  tests/test_inheritance_invariant.py::TestProperty::test_inherited_invariant_on_setter \
  tests/test_inheritance_invariant.py::TestProperty::test_inherited_setter; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
