#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_session.py::TestArtifactSandboxSession::test_run_with_plotting_disabled \
  tests/test_session.py::TestArtifactSandboxSession::test_run_with_plotting_enabled_supported_language \
  tests/test_session.py::TestCreateSession::test_check_dependency_docker_missing \
  tests/test_session.py::TestCreateSession::test_check_dependency_kubernetes_missing \
  tests/test_session.py::TestCreateSession::test_check_dependency_podman_missing \
  tests/test_session.py::TestCreateSession::test_create_docker_session \
  tests/test_session.py::TestCreateSession::test_create_kubernetes_session \
  tests/test_session.py::TestCreateSession::test_create_podman_session \
  tests/test_session.py::TestCreateSession::test_create_micromamba_session \
  tests/test_session.py::TestCreateSession::test_unsupported_backend \
  tests/test_session.py::TestCreateSession::test_sandbox_session_alias \
  tests/test_session.py::TestArtifactSandboxSession::test_init_with_defaults \
  tests/test_session.py::TestArtifactSandboxSession::test_init_with_custom_params \
  tests/test_session.py::TestArtifactSandboxSession::test_context_manager_enter \
  tests/test_session.py::TestArtifactSandboxSession::test_context_manager_exit \
  tests/test_session.py::TestArtifactSandboxSession::test_getattr_delegation \
  tests/test_session.py::TestArtifactSandboxSession::test_run_with_plotting_enabled_unsupported_language \
  tests/test_session.py::TestArtifactSandboxSession::test_run_with_custom_timeout \
  tests/test_session.py::TestSessionConfig::test_image_and_dockerfile_both_provided \
  tests/test_session.py::TestSessionConfig::test_container_id_with_dockerfile \
  tests/test_session.py::TestSessionConfig::test_valid_config_combinations; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
