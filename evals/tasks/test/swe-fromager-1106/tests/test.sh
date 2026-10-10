#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_dependency_graph.py::test_remove_dependency_cascades_orphans \
  tests/test_dependency_graph.py::test_remove_dependency_diamond_sequential \
  tests/test_dependency_graph.py::test_remove_dependency_mid_graph_cascades \
  tests/test_dependency_graph.py::test_remove_dependency_shared_child_kept_by_other_subtree \
  tests/test_dependency_graph.py::test_remove_dependency_cascades_through_diamond \
  tests/test_dependency_graph.py::test_dependencynode_compare \
  tests/test_dependency_graph.py::test_dependencynode_hash \
  tests/test_dependency_graph.py::test_dependencynode_dataclass \
  tests/test_dependency_graph.py::test_iter_requirements \
  tests/test_dependency_graph.py::test_pr759_discussion \
  tests/test_dependency_graph.py::test_tracking_topology_sorter \
  tests/test_dependency_graph.py::test_tracking_topology_sorter_cyclic_error \
  tests/test_dependency_graph.py::test_tracking_topology_sorter_not_passed_out_error \
  tests/test_dependency_graph.py::test_tracking_topology_sorter_not_active_error \
  tests/test_dependency_graph.py::test_e2e_parallel_graph \
  tests/test_dependency_graph.py::test_tracking_topology_sorter_concurrent_access \
  tests/test_dependency_graph.py::test_tracking_topology_sorter_empty_graph \
  tests/test_dependency_graph.py::test_remove_dependency_basic \
  tests/test_dependency_graph.py::test_remove_dependency_keeps_shared_children \
  tests/test_dependency_graph.py::test_remove_dependency_already_removed_child \
  tests/test_dependency_graph.py::test_remove_dependency_nonexistent; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
