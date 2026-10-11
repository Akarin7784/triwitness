#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_concatenation_variable_names \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_creation \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_generating_object \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_reachable_object \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_useless_removal \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_nullable_object \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_remove_epsilon \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_unit_pair \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_cnf \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_substitution \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_union \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_concatenation \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_closure \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_pos_closure \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_reverse \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_emptiness \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_membership \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_to_pda \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_conversions \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_profiling_conversions \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_generation_words \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_generation_words2 \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_finite \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_intersection \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_intersection_empty \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_intersection_dfa \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_intersection_with_epsilon \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_intersection_dfa2 \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_profiling_intersection \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_pda_object_creator \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_string_variable \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_get_leftmost_derivation \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_get_rightmost_derivation \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_derivation_does_not_exist \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_derivation_empty \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_from_text \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_from_text2 \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_from_text_union \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_epsilon \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_epsilon2 \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_generate_epsilon \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_change_starting_variable \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_is_not_normal_form \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_is_normal_form \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_to_text \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_to_text_cnf \
  pyformlang/cfg/tests/test_cfg.py::TestCFG::test_to_text_epsilon; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
