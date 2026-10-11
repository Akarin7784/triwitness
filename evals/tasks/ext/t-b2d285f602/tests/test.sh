#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_plugin_class_warns \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_unused_kwargs_throws \
  distributed/diagnostics/tests/test_worker_plugin.py::test_create_with_client_and_plugin_from_class \
  distributed/diagnostics/tests/test_worker_plugin.py::test_plugin_class_warns \
  distributed/diagnostics/tests/test_worker_plugin.py::test_unused_kwargs_throws \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_simple \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_add_remove_worker \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_async_add_remove_worker \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_add_by_type \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_register_scheduler_plugin \
  distributed/diagnostics/tests/test_scheduler_plugin.py::test_register_scheduler_plugin_pickle_disabled \
  distributed/diagnostics/tests/test_worker_plugin.py::test_create_with_client \
  distributed/diagnostics/tests/test_worker_plugin.py::test_remove_with_client \
  distributed/diagnostics/tests/test_worker_plugin.py::test_remove_with_client_raises \
  distributed/diagnostics/tests/test_worker_plugin.py::test_create_on_construction \
  distributed/diagnostics/tests/test_worker_plugin.py::test_normal_task_transitions_called \
  distributed/diagnostics/tests/test_worker_plugin.py::test_failing_task_transitions_called \
  distributed/diagnostics/tests/test_worker_plugin.py::test_superseding_task_transitions_called \
  distributed/diagnostics/tests/test_worker_plugin.py::test_dependent_tasks \
  distributed/diagnostics/tests/test_worker_plugin.py::test_empty_plugin \
  distributed/diagnostics/tests/test_worker_plugin.py::test_default_name \
  distributed/diagnostics/tests/test_worker_plugin.py::test_release_key_deprecated \
  distributed/diagnostics/tests/test_worker_plugin.py::test_WorkerPlugin_overwrite; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
