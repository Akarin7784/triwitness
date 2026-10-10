#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_platform_requires_error \
  'test/integration/graph/test_system_tools.py::TestToolRequires::test_system_tool_require[]' \
  'test/integration/graph/test_system_tools.py::TestToolRequires::test_system_tool_require[#myrev]' \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_system_tool_require_non_matching \
  'test/integration/graph/test_system_tools.py::TestToolRequires::test_system_tool_require_range[]' \
  'test/integration/graph/test_system_tools.py::TestToolRequires::test_system_tool_require_range[#myrev]' \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_system_tool_require_range_non_matching \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_system_tool_require_no_host \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_graph_info_system_tool_require_range \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_consumer_resolved_version \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_consumer_resolved_revision \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_consumer_unresolved_revision \
  test/integration/graph/test_system_tools.py::TestToolRequires::test_require_build_context \
  'test/integration/graph/test_system_tools.py::TestToolRequiresLock::test_system_tool_require_range[]' \
  'test/integration/graph/test_system_tools.py::TestToolRequiresLock::test_system_tool_require_range[#myrev]' \
  test/integration/graph/test_system_tools.py::TestGenerators::test_system_tool_require_range \
  'test/integration/graph/test_system_tools.py::TestPackageID::test_package_id_modes[recipe_revision_mode]' \
  'test/integration/graph/test_system_tools.py::TestPackageID::test_package_id_modes[full_package_mode]' \
  test/integration/graph/test_system_tools.py::TestPackageID::test_package_id_explicit_revision; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
