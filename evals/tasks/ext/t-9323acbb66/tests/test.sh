#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_world.py::test_adding_component_to_not_existing_entity_raises_error \
  tests/test_world.py::test_delete_entity \
  tests/test_world.py::TestEntityExists::test_empty_entity \
  tests/test_world.py::test_world_instantiation \
  tests/test_world.py::test_create_entity \
  tests/test_world.py::test_create_entity_with_components \
  tests/test_world.py::test_create_entity_and_add_components \
  tests/test_world.py::test_create_entity_and_add_components_with_alias \
  tests/test_world.py::test_component_for_entity \
  tests/test_world.py::test_components_for_entity \
  tests/test_world.py::test_has_component \
  tests/test_world.py::test_has_components \
  tests/test_world.py::test_get_component \
  tests/test_world.py::test_get_two_components \
  tests/test_world.py::test_get_three_components \
  tests/test_world.py::test_try_component \
  tests/test_world.py::test_try_components \
  tests/test_world.py::test_clear_database \
  tests/test_world.py::test_add_processor \
  tests/test_world.py::test_remove_processor \
  tests/test_world.py::test_get_processor \
  tests/test_world.py::test_processor_args \
  tests/test_world.py::test_processor_kwargs \
  tests/test_world.py::test_clear_cache \
  tests/test_world.py::test_cache_results \
  tests/test_world.py::TestEntityExists::test_dead_entity \
  tests/test_world.py::TestEntityExists::test_not_created_entity \
  tests/test_world.py::TestEntityExists::test_entity_with_component \
  tests/test_world.py::test_event_dispatch_no_handlers \
  tests/test_world.py::test_event_dispatch_one_arg \
  tests/test_world.py::test_event_dispatch_two_args \
  tests/test_world.py::test_event_dispatch_incorrect_args \
  tests/test_world.py::test_set_methoad_as_handler_in_init \
  tests/test_world.py::test_set_instance_methoad_as_handler; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
