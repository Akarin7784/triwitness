#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_types_structure.py::test_codegen_make_init \
  tests/test_types_structure.py::test_codegen_hashable \
  tests/test_types_union.py::test_codegen_hashable \
  tests/test_types_structure.py::test_structure \
  tests/test_types_structure.py::test_structure_read \
  tests/test_types_structure.py::test_structure_write \
  tests/test_types_structure.py::test_structure_array_read \
  tests/test_types_structure.py::test_structure_array_write \
  tests/test_types_structure.py::test_structure_modify \
  tests/test_types_structure.py::test_structure_single_byte_field \
  tests/test_types_structure.py::test_structure_same_name_method \
  tests/test_types_structure.py::test_structure_bool \
  tests/test_types_structure.py::test_structure_cmp \
  tests/test_types_structure.py::test_structure_repr \
  tests/test_types_structure.py::test_structure_eof \
  'tests/test_types_structure.py::test_structure_definitions[True]' \
  'tests/test_types_structure.py::test_structure_definitions[False]' \
  'tests/test_types_structure.py::test_structure_definition_simple[True]' \
  'tests/test_types_structure.py::test_structure_definition_simple[False]' \
  'tests/test_types_structure.py::test_structure_definition_simple_be[True]' \
  'tests/test_types_structure.py::test_structure_definition_simple_be[False]' \
  'tests/test_types_structure.py::test_structure_definition_expressions[True]' \
  'tests/test_types_structure.py::test_structure_definition_expressions[False]' \
  'tests/test_types_structure.py::test_structure_definition_sizes[True]' \
  'tests/test_types_structure.py::test_structure_definition_sizes[False]' \
  'tests/test_types_structure.py::test_structure_definition_nested[True]' \
  'tests/test_types_structure.py::test_structure_definition_nested[False]' \
  'tests/test_types_structure.py::test_structure_definition_write[True]' \
  'tests/test_types_structure.py::test_structure_definition_write[False]' \
  'tests/test_types_structure.py::test_structure_definition_write_be[True]' \
  'tests/test_types_structure.py::test_structure_definition_write_be[False]' \
  tests/test_types_structure.py::test_structure_definition_write_anonymous \
  'tests/test_types_structure.py::test_structure_field_discard[True]' \
  'tests/test_types_structure.py::test_structure_field_discard[False]' \
  tests/test_types_structure.py::test_structure_field_duplicate \
  tests/test_types_structure.py::test_structure_definition_self \
  tests/test_types_structure.py::test_align_struct_in_struct \
  'tests/test_types_structure.py::test_structure_default[True]' \
  'tests/test_types_structure.py::test_structure_default[False]' \
  'tests/test_types_structure.py::test_structure_default_dynamic[True]' \
  'tests/test_types_structure.py::test_structure_default_dynamic[False]' \
  tests/test_types_structure.py::test_structure_partial_initialization \
  tests/test_types_union.py::test_union \
  tests/test_types_union.py::test_union_read \
  tests/test_types_union.py::test_union_read_offset \
  tests/test_types_union.py::test_union_write \
  tests/test_types_union.py::test_union_write_anonymous \
  tests/test_types_union.py::test_union_array_read \
  tests/test_types_union.py::test_union_array_write \
  tests/test_types_union.py::test_union_modify \
  tests/test_types_union.py::test_union_bool \
  tests/test_types_union.py::test_union_cmp \
  tests/test_types_union.py::test_union_repr \
  tests/test_types_union.py::test_union_eof \
  tests/test_types_union.py::test_union_definition \
  'tests/test_types_union.py::test_union_definition_nested[True]' \
  'tests/test_types_union.py::test_union_definition_nested[False]' \
  'tests/test_types_union.py::test_union_definition_anonymous[True]' \
  'tests/test_types_union.py::test_union_definition_anonymous[False]' \
  tests/test_types_union.py::test_union_definition_dynamic \
  tests/test_types_union.py::test_union_update \
  tests/test_types_union.py::test_union_nested_update \
  tests/test_types_union.py::test_union_anonymous_update \
  tests/test_types_union.py::test_union_default \
  tests/test_types_union.py::test_union_default_dynamic \
  tests/test_types_union.py::test_union_partial_initialization \
  tests/test_types_union.py::test_union_partial_initialization_dynamic; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
