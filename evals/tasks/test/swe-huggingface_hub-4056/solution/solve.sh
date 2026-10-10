#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p src/huggingface_hub
cat > src/huggingface_hub/_snapshot_download.py <<'TW_EOF'
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, overload

import httpx
from tqdm.auto import tqdm as base_tqdm
from tqdm.contrib.concurrent import thread_map

from . import constants
from .errors import (
    DryRunError,
    GatedRepoError,
    HfHubHTTPError,
    LocalEntryNotFoundError,
    RepositoryNotFoundError,
    RevisionNotFoundError,
)
from .file_download import REGEX_COMMIT_HASH, DryRunFileInfo, hf_hub_download, repo_folder_name
from .hf_api import DatasetInfo, HfApi, ModelInfo, RepoFile, SpaceInfo
from .utils import OfflineModeIsEnabled, filter_repo_objects, logging, validate_hf_hub_args
from .utils.tqdm import _create_progress_bar
from .utils.tqdm import tqdm as hf_tqdm


logger = logging.get_logger(__name__)

LARGE_REPO_THRESHOLD = 1000  # After this limit, we don't consider `repo_info.siblings` to be reliable enough


@overload
def snapshot_download(
    repo_id: str,
    *,
    repo_type: str | None = None,
    revision: str | None = None,
    cache_dir: str | Path | None = None,
    local_dir: str | Path | None = None,
    library_name: str | None = None,
    library_version: str | None = None,
    user_agent: dict | str | None = None,
    etag_timeout: float = constants.DEFAULT_ETAG_TIMEOUT,
    force_download: bool = False,
    token: bool | str | None = None,
    local_files_only: bool = False,
    allow_patterns: list[str] | str | None = None,
    ignore_patterns: list[str] | str | None = None,
    max_workers: int = 8,
    tqdm_class: type[base_tqdm] | None = None,
    headers: dict[str, str] | None = None,
    endpoint: str | None = None,
    dry_run: Literal[False] = False,
) -> str: ...


@overload
def snapshot_download(
    repo_id: str,
    *,
    repo_type: str | None = None,
    revision: str | None = None,
    cache_dir: str | Path | None = None,
    local_dir: str | Path | None = None,
    library_name: str | None = None,
    library_version: str | None = None,
    user_agent: dict | str | None = None,
    etag_timeout: float = constants.DEFAULT_ETAG_TIMEOUT,
    force_download: bool = False,
    token: bool | str | None = None,
    local_files_only: bool = False,
    allow_patterns: list[str] | str | None = None,
    ignore_patterns: list[str] | str | None = None,
    max_workers: int = 8,
    tqdm_class: type[base_tqdm] | None = None,
    headers: dict[str, str] | None = None,
    endpoint: str | None = None,
    dry_run: Literal[True] = True,
) -> list[DryRunFileInfo]: ...


@overload
def snapshot_download(
    repo_id: str,
    *,
    repo_type: str | None = None,
    revision: str | None = None,
    cache_dir: str | Path | None = None,
    local_dir: str | Path | None = None,
    library_name: str | None = None,
    library_version: str | None = None,
    user_agent: dict | str | None = None,
    etag_timeout: float = constants.DEFAULT_ETAG_TIMEOUT,
    force_download: bool = False,
    token: bool | str | None = None,
    local_files_only: bool = False,
    allow_patterns: list[str] | str | None = None,
    ignore_patterns: list[str] | str | None = None,
    max_workers: int = 8,
    tqdm_class: type[base_tqdm] | None = None,
    headers: dict[str, str] | None = None,
    endpoint: str | None = None,
    dry_run: bool = False,
) -> str | list[DryRunFileInfo]: ...


@validate_hf_hub_args
def snapshot_download(
    repo_id: str,
    *,
    repo_type: str | None = None,
    revision: str | None = None,
    cache_dir: str | Path | None = None,
    local_dir: str | Path | None = None,
    library_name: str | None = None,
    library_version: str | None = None,
    user_agent: dict | str | None = None,
    etag_timeout: float = constants.DEFAULT_ETAG_TIMEOUT,
    force_download: bool = False,
    token: bool | str | None = None,
    local_files_only: bool = False,
    allow_patterns: list[str] | str | None = None,
    ignore_patterns: list[str] | str | None = None,
    max_workers: int = 8,
    tqdm_class: type[base_tqdm] | None = None,
    headers: dict[str, str] | None = None,
    endpoint: str | None = None,
    dry_run: bool = False,
) -> str | list[DryRunFileInfo]:
    """Download repo files.

    Download a whole snapshot of a repo's files at the specified revision. This is useful when you want all files from
    a repo, because you don't know which ones you will need a priori. All files are nested inside a folder in order
    to keep their actual filename relative to that folder. You can also filter which files to download using
    `allow_patterns` and `ignore_patterns`.

    If `local_dir` is provided, the file structure from the repo will be replicated in this location. When using this
    option, the `cache_dir` will not be used and a `.cache/huggingface/` folder will be created at the root of `local_dir`
    to store some metadata related to the downloaded files. While this mechanism is not as robust as the main
    cache-system, it's optimized for regularly pulling the latest version of a repository.

    An alternative would be to clone the repo but this requires git and git-lfs to be installed and properly
    configured. It is also not possible to filter which files to download when cloning a repository using git.

    Args:
        repo_id (`str`):
            A user or an organization name and a repo name separated by a `/`.
        repo_type (`str`, *optional*):
            Set to `"dataset"` or `"space"` if downloading from a dataset or space,
            `None` or `"model"` if downloading from a model. Default is `None`.
        revision (`str`, *optional*):
            An optional Git revision id which can be a branch name, a tag, or a
            commit hash.
        cache_dir (`str`, `Path`, *optional*):
            Path to the folder where cached files are stored.
        local_dir (`str` or `Path`, *optional*):
            If provided, the downloaded files will be placed under this directory.
        library_name (`str`, *optional*):
            The name of the library to which the object corresponds.
        library_version (`str`, *optional*):
            The version of the library.
        user_agent (`str`, `dict`, *optional*):
            The user-agent info in the form of a dictionary or a string.
        etag_timeout (`float`, *optional*, defaults to `10`):
            When fetching ETag, how many seconds to wait for the server to send
            data before giving up which is passed to `httpx.request`.
        force_download (`bool`, *optional*, defaults to `False`):
            Whether the file should be downloaded even if it already exists in the local cache.
        token (`str`, `bool`, *optional*):
            A token to be used for the download.
                - If `True`, the token is read from the HuggingFace config
                  folder.
                - If a string, it's used as the authentication token.
        headers (`dict`, *optional*):
            Additional headers to include in the request. Those headers take precedence over the others.
        local_files_only (`bool`, *optional*, defaults to `False`):
            If `True`, avoid downloading the file and return the path to the
            local cached file if it exists.
        allow_patterns (`list[str]` or `str`, *optional*):
            If provided, only files matching at least one pattern are downloaded.
        ignore_patterns (`list[str]` or `str`, *optional*):
            If provided, files matching any of the patterns are not downloaded.
        max_workers (`int`, *optional*):
            Number of concurrent threads to download files (1 thread = 1 file download).
            Defaults to 8.
        tqdm_class (`tqdm`, *optional*):
            If provided, overwrites the default behavior for the progress bar. Passed
            argument must inherit from `tqdm.auto.tqdm` or at least mimic its behavior.
            Note that the `tqdm_class` is not passed to each individual download.
            Defaults to the custom HF progress bar that can be disabled by setting
            `HF_HUB_DISABLE_PROGRESS_BARS` environment variable.
        dry_run (`bool`, *optional*, defaults to `False`):
            If `True`, perform a dry run without actually downloading the files. Returns a list of
            [`DryRunFileInfo`] objects containing information about what would be downloaded.

    Returns:
        `str` or list of [`DryRunFileInfo`]:
            - If `dry_run=False`: Local snapshot path.
            - If `dry_run=True`: A list of [`DryRunFileInfo`] objects containing download information.

    Raises:
        [`~utils.RepositoryNotFoundError`]
            If the repository to download from cannot be found. This may be because it doesn't exist,
            or because it is set to `private` and you do not have access.
        [`~utils.RevisionNotFoundError`]
            If the revision to download from cannot be found.
        [`EnvironmentError`](https://docs.python.org/3/library/exceptions.html#EnvironmentError)
            If `token=True` and the token cannot be found.
        [`OSError`](https://docs.python.org/3/library/exceptions.html#OSError) if
            ETag cannot be determined.
        [`ValueError`](https://docs.python.org/3/library/exceptions.html#ValueError)
            if some parameter value is invalid.
    """
    if cache_dir is None:
        cache_dir = constants.HF_HUB_CACHE
    if revision is None:
        revision = constants.DEFAULT_REVISION
    if isinstance(cache_dir, Path):
        cache_dir = str(cache_dir)

    if repo_type is None:
        repo_type = "model"
    if repo_type not in constants.REPO_TYPES:
        raise ValueError(f"Invalid repo type: {repo_type}. Accepted repo types are: {str(constants.REPO_TYPES)}")

    storage_folder = os.path.join(cache_dir, repo_folder_name(repo_id=repo_id, repo_type=repo_type))

    api = HfApi(
        library_name=library_name,
        library_version=library_version,
        user_agent=user_agent,
        endpoint=endpoint,
        headers=headers,
        token=token,
    )

    repo_info: ModelInfo | DatasetInfo | SpaceInfo | None = None
    api_call_error: Exception | None = None
    if not local_files_only:
        # try/except logic to handle different errors => taken from `hf_hub_download`
        try:
            # if we have internet connection we want to list files to download
            repo_info = api.repo_info(repo_id=repo_id, repo_type=repo_type, revision=revision)
        except httpx.ProxyError:
            # Actually raise on proxy error
            raise
        except (httpx.ConnectError, httpx.TimeoutException, OfflineModeIsEnabled) as error:
            # Internet connection is down
            # => will try to use local files only
            api_call_error = error
            pass
        except RevisionNotFoundError:
            # The repo was found but the revision doesn't exist on the Hub (never existed or got deleted)
            raise
        except HfHubHTTPError as error:
            # Multiple reasons for an http error:
            # - Repository is private and invalid/missing token sent
            # - Repository is gated and invalid/missing token sent
            # - Hub is down (error 500 or 504)
            # => let's switch to 'local_files_only=True' to check if the files are already cached.
            #    (if it's not the case, the error will be re-raised)
            api_call_error = error
            pass

    # At this stage, if `repo_info` is None it means either:
    # - internet connection is down
    # - internet connection is deactivated (local_files_only=True or HF_HUB_OFFLINE=True)
    # - repo is private/gated and invalid/missing token sent
    # - Hub is down
    # => let's look if we can find the appropriate folder in the cache:
    #    - if the specified revision is a commit hash, look inside "snapshots".
    #    - f the specified revision is a branch or tag, look inside "refs".
    # => if local_dir is not None, we will return the path to the local folder if it exists.
    if repo_info is None:
        if dry_run:
            raise DryRunError(
                "Dry run cannot be performed as the repository cannot be accessed. Please check your internet connection or authentication token."
            ) from api_call_error

        # Try to get which commit hash corresponds to the specified revision
        commit_hash = None
        if REGEX_COMMIT_HASH.match(revision):
            commit_hash = revision
        else:
            ref_path = os.path.join(storage_folder, "refs", revision)
            if os.path.exists(ref_path):
                # retrieve commit_hash from refs file
                with open(ref_path) as f:
                    commit_hash = f.read()

        # Try to locate snapshot folder for this commit hash
        if commit_hash is not None and local_dir is None:
            snapshot_folder = os.path.join(storage_folder, "snapshots", commit_hash)
            if os.path.exists(snapshot_folder):
                # Snapshot folder exists => let's return it
                # (but we can't check if all the files are actually there)
                return snapshot_folder

        # If local_dir is not None, return it if it exists and is not empty
        if local_dir is not None:
            local_dir = Path(local_dir)
            if local_dir.is_dir() and any(local_dir.iterdir()):
                logger.warning(
                    f"Returning existing local_dir `{local_dir}` as remote repo cannot be accessed in `snapshot_download` ({api_call_error})."
                )
                return str(local_dir.resolve())
        # If we couldn't find the appropriate folder on disk, raise an error.
        if local_files_only:
            raise LocalEntryNotFoundError(
                "Cannot find an appropriate cached snapshot folder for the specified revision on the local disk and "
                "outgoing traffic has been disabled. To enable repo look-ups and downloads online, pass "
                "'local_files_only=False' as input."
            )
        elif isinstance(api_call_error, OfflineModeIsEnabled):
            raise LocalEntryNotFoundError(
                "Cannot find an appropriate cached snapshot folder for the specified revision on the local disk and "
                "outgoing traffic has been disabled. To enable repo look-ups and downloads online, set "
                "'HF_HUB_OFFLINE=0' as environment variable."
            ) from api_call_error
        elif isinstance(api_call_error, (RepositoryNotFoundError, GatedRepoError)) or (
            isinstance(api_call_error, HfHubHTTPError) and api_call_error.response.status_code == 401
        ):
            # Repo not found, gated, or specific authentication error => let's raise the actual error
            raise api_call_error
        else:
            # Otherwise: most likely a connection issue or Hub downtime => let's warn the user
            raise LocalEntryNotFoundError(
                f"Got: {api_call_error.__class__.__name__}: {api_call_error}"
                "\nAn error happened while trying to locate the files on the Hub and we cannot find the appropriate"
                " snapshot folder for the specified revision on the local disk. Please check your internet connection"
                " and try again."
            ) from api_call_error

    # At this stage, internet connection is up and running
    # => let's download the files!
    assert repo_info.sha is not None, "Repo info returned from server must have a revision sha."

    # Corner case: on very large repos, the siblings list in `repo_info` might not contain all files.
    # In that case, we need to use the `list_repo_tree` method to prevent caching issues.
    repo_files: Iterable[str] = [f.rfilename for f in repo_info.siblings] if repo_info.siblings is not None else []
    unreliable_nb_files = (
        repo_info.siblings is None or len(repo_info.siblings) == 0 or len(repo_info.siblings) > LARGE_REPO_THRESHOLD
    )
    if unreliable_nb_files:
        logger.info(
            "Number of files in the repo is unreliable. Using `list_repo_tree` to ensure all files are listed."
        )
        repo_files = (
            f.rfilename
            for f in api.list_repo_tree(repo_id=repo_id, recursive=True, revision=revision, repo_type=repo_type)
            if isinstance(f, RepoFile)
        )

    filtered_repo_files: Iterable[str] = filter_repo_objects(
        items=repo_files,
        allow_patterns=allow_patterns,
        ignore_patterns=ignore_patterns,
    )

    if not unreliable_nb_files:
        filtered_repo_files = list(filtered_repo_files)
        tqdm_desc = f"Fetching {len(filtered_repo_files)} files"
    else:
        tqdm_desc = "Fetching ... files"
    if dry_run:
        tqdm_desc = "[dry-run] " + tqdm_desc

    commit_hash = repo_info.sha
    snapshot_folder = os.path.join(storage_folder, "snapshots", commit_hash)
    # if passed revision is not identical to commit_hash
    # then revision has to be a branch name or tag name.
    # In that case store a ref.
    if revision != commit_hash:
        ref_path = os.path.join(storage_folder, "refs", revision)
        try:
            os.makedirs(os.path.dirname(ref_path), exist_ok=True)
            with open(ref_path, "w") as f:
                f.write(commit_hash)
        except OSError as e:
            logger.warning(f"Ignored error while writing commit hash to {ref_path}: {e}.")

    results: list[str | DryRunFileInfo] = []

    # User can use its own tqdm class or the default one from `huggingface_hub.utils`
    tqdm_class = tqdm_class or hf_tqdm

    # Create a progress bar for the bytes downloaded
    # This progress bar is shared across threads/files and gets updated each time we fetch
    # metadata for a file.
    bytes_progress = _create_progress_bar(
        cls=tqdm_class,
        log_level=logger.getEffectiveLevel(),
        name="huggingface_hub.snapshot_download",
        desc="Downloading (incomplete total...)",
        total=0,
        initial=0,
        unit="B",
        unit_scale=True,
    )

    class _AggregatedTqdm:
        """Fake tqdm object to aggregate progress into the parent `bytes_progress` bar.

        In practice the `_AggregatedTqdm` object won't be displayed, it's just used to update
        the `bytes_progress` bar from each thread/file download.
        """

        def __init__(self, *args, **kwargs):
            # Adjust the total of the parent progress bar
            total = kwargs.pop("total", None)
            if total is not None:
                bytes_progress.total += total
                bytes_progress.refresh()

            # Adjust initial of the parent progress bar
            initial = kwargs.pop("initial", 0)
            if initial:
                bytes_progress.update(initial)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def update(self, n: int | float | None = 1) -> None:
            bytes_progress.update(n)

    # we pass the commit_hash to hf_hub_download
    # so no network call happens if we already
    # have the file locally.
    def _inner_hf_hub_download(repo_file: str) -> None:
        results.append(
            hf_hub_download(  # type: ignore
                repo_id,
                filename=repo_file,
                repo_type=repo_type,
                revision=commit_hash,
                endpoint=endpoint,
                cache_dir=cache_dir,
                local_dir=local_dir,
                library_name=library_name,
                library_version=library_version,
                user_agent=user_agent,
                etag_timeout=etag_timeout,
                force_download=force_download,
                token=token,
                headers=headers,
                tqdm_class=_AggregatedTqdm,  # type: ignore
                dry_run=dry_run,
            )
        )

    thread_map(
        _inner_hf_hub_download,
        filtered_repo_files,
        desc=tqdm_desc,
        max_workers=max_workers,
        tqdm_class=tqdm_class,
    )

    bytes_progress.set_description("Download complete")

    if dry_run:
        assert all(isinstance(r, DryRunFileInfo) for r in results)
        return results  # type: ignore

    if local_dir is not None:
        return str(os.path.realpath(local_dir))
    return snapshot_folder
TW_EOF
mkdir -p src/huggingface_hub/utils
cat > src/huggingface_hub/utils/tqdm.py <<'TW_EOF'
# Copyright 2021 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
"""Utility helpers to handle progress bars in `huggingface_hub`.

Example:
    1. Use `huggingface_hub.utils.tqdm` as you would use `tqdm.tqdm` or `tqdm.auto.tqdm`.
    2. To disable progress bars, either use `disable_progress_bars()` helper or set the
       environment variable `HF_HUB_DISABLE_PROGRESS_BARS` to 1.
    3. To re-enable progress bars, use `enable_progress_bars()`.
    4. To check whether progress bars are disabled, use `are_progress_bars_disabled()`.

NOTE: Environment variable `HF_HUB_DISABLE_PROGRESS_BARS` has the priority.

Example:
    ```py
    >>> from huggingface_hub.utils import are_progress_bars_disabled, disable_progress_bars, enable_progress_bars, tqdm

    # Disable progress bars globally
    >>> disable_progress_bars()

    # Use as normal `tqdm`
    >>> for _ in tqdm(range(5)):
    ...    pass

    # Still not showing progress bars, as `disable=False` is overwritten to `True`.
    >>> for _ in tqdm(range(5), disable=False):
    ...    pass

    >>> are_progress_bars_disabled()
    True

    # Re-enable progress bars globally
    >>> enable_progress_bars()

    # Progress bar will be shown !
    >>> for _ in tqdm(range(5)):
    ...   pass
    100%|███████████████████████████████████████| 5/5 [00:00<00:00, 117817.53it/s]
    ```

Group-based control:
    ```python
    # Disable progress bars for a specific group
    >>> disable_progress_bars("peft.foo")

    # Check state of different groups
    >>> assert not are_progress_bars_disabled("peft"))
    >>> assert not are_progress_bars_disabled("peft.something")
    >>> assert are_progress_bars_disabled("peft.foo"))
    >>> assert are_progress_bars_disabled("peft.foo.bar"))

    # Enable progress bars for a subgroup
    >>> enable_progress_bars("peft.foo.bar")

    # Check if enabling a subgroup affects the parent group
    >>> assert are_progress_bars_disabled("peft.foo"))
    >>> assert not are_progress_bars_disabled("peft.foo.bar"))

    # No progress bar for `name="peft.foo"`
    >>> for _ in tqdm(range(5), name="peft.foo"):
    ...     pass

    # Progress bar will be shown for `name="peft.foo.bar"`
    >>> for _ in tqdm(range(5), name="peft.foo.bar"):
    ...     pass
    100%|███████████████████████████████████████| 5/5 [00:00<00:00, 117817.53it/s]

    ```
"""

import io
import logging
import os
import warnings
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import ContextManager

from tqdm.auto import tqdm as old_tqdm

from ..constants import HF_HUB_DISABLE_PROGRESS_BARS


# The `HF_HUB_DISABLE_PROGRESS_BARS` environment variable can be True, False, or not set (None),
# allowing for control over progress bar visibility. When set, this variable takes precedence
# over programmatic settings, dictating whether progress bars should be shown or hidden globally.
# Essentially, the environment variable's setting overrides any code-based configurations.
#
# If `HF_HUB_DISABLE_PROGRESS_BARS` is not defined (None), it implies that users can manage
# progress bar visibility through code. By default, progress bars are turned on.


progress_bar_states: dict[str, bool] = {}


def disable_progress_bars(name: str | None = None) -> None:
    """
    Disable progress bars either globally or for a specified group.

    This function updates the state of progress bars based on a group name.
    If no group name is provided, all progress bars are disabled. The operation
    respects the `HF_HUB_DISABLE_PROGRESS_BARS` environment variable's setting.

    Args:
        name (`str`, *optional*):
            The name of the group for which to disable the progress bars. If None,
            progress bars are disabled globally.

    Raises:
        Warning: If the environment variable precludes changes.
    """
    if HF_HUB_DISABLE_PROGRESS_BARS is False:
        warnings.warn(
            "Cannot disable progress bars: environment variable `HF_HUB_DISABLE_PROGRESS_BARS=0` is set and has priority."
        )
        return

    if name is None:
        progress_bar_states.clear()
        progress_bar_states["_global"] = False
    else:
        keys_to_remove = [key for key in progress_bar_states if key.startswith(f"{name}.")]
        for key in keys_to_remove:
            del progress_bar_states[key]
        progress_bar_states[name] = False


def enable_progress_bars(name: str | None = None) -> None:
    """
    Enable progress bars either globally or for a specified group.

    This function sets the progress bars to enabled for the specified group or globally
    if no group is specified. The operation is subject to the `HF_HUB_DISABLE_PROGRESS_BARS`
    environment setting.

    Args:
        name (`str`, *optional*):
            The name of the group for which to enable the progress bars. If None,
            progress bars are enabled globally.

    Raises:
        Warning: If the environment variable precludes changes.
    """
    if HF_HUB_DISABLE_PROGRESS_BARS is True:
        warnings.warn(
            "Cannot enable progress bars: environment variable `HF_HUB_DISABLE_PROGRESS_BARS=1` is set and has priority."
        )
        return

    if name is None:
        progress_bar_states.clear()
        progress_bar_states["_global"] = True
    else:
        keys_to_remove = [key for key in progress_bar_states if key.startswith(f"{name}.")]
        for key in keys_to_remove:
            del progress_bar_states[key]
        progress_bar_states[name] = True


def are_progress_bars_disabled(name: str | None = None) -> bool:
    """
    Check if progress bars are disabled globally or for a specific group.

    This function returns whether progress bars are disabled for a given group or globally.
    It checks the `HF_HUB_DISABLE_PROGRESS_BARS` environment variable first, then the programmatic
    settings.

    Args:
        name (`str`, *optional*):
            The group name to check; if None, checks the global setting.

    Returns:
        `bool`: True if progress bars are disabled, False otherwise.
    """
    if HF_HUB_DISABLE_PROGRESS_BARS is True:
        return True

    if name is None:
        return not progress_bar_states.get("_global", True)

    while name:
        if name in progress_bar_states:
            return not progress_bar_states[name]
        name = ".".join(name.split(".")[:-1])

    return not progress_bar_states.get("_global", True)


def is_tqdm_disabled(log_level: int) -> bool | None:
    """
    Determine if tqdm progress bars should be disabled based on logging level and environment settings.

    see https://github.com/huggingface/huggingface_hub/pull/2000 and https://github.com/huggingface/huggingface_hub/pull/2698.
    """
    if log_level == logging.NOTSET:
        return True
    if os.getenv("TQDM_POSITION") == "-1":
        return False
    return None


class tqdm(old_tqdm):
    """
    Class to override `disable` argument in case progress bars are globally disabled.

    Taken from https://github.com/tqdm/tqdm/issues/619#issuecomment-619639324.
    """

    def __init__(self, *args, **kwargs):
        name = kwargs.pop("name", None)  # do not pass `name` to `tqdm`
        if are_progress_bars_disabled(name):
            kwargs["disable"] = True
        super().__init__(*args, **kwargs)

    def __delattr__(self, attr: str) -> None:
        """Fix for https://github.com/huggingface/huggingface_hub/issues/1603"""
        try:
            super().__delattr__(attr)
        except AttributeError:
            if attr != "_lock":
                raise


@contextmanager
def tqdm_stream_file(path: Path | str) -> Iterator[io.BufferedReader]:
    """
    Open a file as binary and wrap the `read` method to display a progress bar when it's streamed.

    First implemented in `transformers` in 2019 but removed when switched to git-lfs. Used in `huggingface_hub` to show
    progress bar when uploading an LFS file to the Hub. See github.com/huggingface/transformers/pull/2078#discussion_r354739608
    for implementation details.

    Note: currently implementation handles only files stored on disk as it is the most common use case. Could be
          extended to stream any `BinaryIO` object but we might have to debug some corner cases.

    Example:
    ```py
    >>> with tqdm_stream_file("config.json") as f:
    >>>     httpx.put(url, data=f)
    config.json: 100%|█████████████████████████| 8.19k/8.19k [00:02<00:00, 3.72kB/s]
    ```
    """
    if isinstance(path, str):
        path = Path(path)

    with path.open("rb") as f:
        total_size = path.stat().st_size
        pbar = tqdm(
            unit="B",
            unit_scale=True,
            total=total_size,
            initial=0,
            desc=path.name,
        )

        f_read = f.read

        def _inner_read(size: int | None = -1) -> bytes:
            data = f_read(size)
            pbar.update(len(data))
            return data

        f.read = _inner_read  # type: ignore

        yield f

        pbar.close()


def _create_progress_bar(*, cls: type[old_tqdm], log_level: int, name: str | None = None, **kwargs) -> old_tqdm:
    """Create a progress bar.

    For our `tqdm` subclass (or subclasses of it): respects all disable signals
    (`HF_HUB_DISABLE_PROGRESS_BARS`, `disable_progress_bars()`, log level) and uses
    `disable=None` for TTY auto-detection (see https://github.com/huggingface/huggingface_hub/pull/2000),
    unless `TQDM_POSITION=-1` forces bars on (https://github.com/huggingface/huggingface_hub/pull/2698).

    For other classes: does not inject `disable` or `name`. the custom class is fully
    responsible for its own behavior. Vanilla tqdm defaults to `disable=False` (bar shows).
    Omits `name` which vanilla tqdm rejects with `TqdmKeyError`. See https://github.com/huggingface/huggingface_hub/issues/4050.
    """
    # issubclass() crashes on non-class callables (e.g. functools.partial), guard with isinstance.
    if not (isinstance(cls, type) and issubclass(cls, tqdm)):
        return cls(**kwargs)  # type: ignore[return-value]

    # HF subclass: keep the historical log-level / TTY behavior. Group-based
    # disabling is already handled in `tqdm.__init__`.
    disable = is_tqdm_disabled(log_level)
    return cls(disable=disable, name=name, **kwargs)  # type: ignore[return-value]


def _get_progress_bar_context(
    *,
    desc: str,
    log_level: int,
    total: int | None = None,
    initial: int = 0,
    unit: str = "B",
    unit_scale: bool = True,
    name: str | None = None,
    tqdm_class: type[old_tqdm] | None = None,
    _tqdm_bar: tqdm | None = None,
) -> ContextManager[tqdm]:
    if _tqdm_bar is not None:
        return nullcontext(_tqdm_bar)
        # ^ `contextlib.nullcontext` mimics a context manager that does nothing
        #   Makes it easier to use the same code path for both cases but in the later
        #   case, the progress bar is not closed when exiting the context manager.

    return _create_progress_bar(  # type: ignore
        cls=tqdm_class or tqdm,
        log_level=log_level,
        name=name,
        unit=unit,
        unit_scale=unit_scale,
        total=total,
        initial=initial,
        desc=desc,
    )
TW_EOF
