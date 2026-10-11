#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p hlp
cat > hlp/cli.py <<'TW_EOF'
import argparse
import importlib
import inspect
import os
import shlex
import sys
from textwrap import dedent

from .compat import builtins, iter_modules
from .typing import MYPY_RUNNING
from .util import getattr_recursive, sequences

if MYPY_RUNNING:
    from typing import Any, Iterable, Iterator, List, Optional, Tuple


class NamedObject(object):
    def __init__(self, name, obj):
        # type: (str, Any) -> None
        self.name = name
        self.obj = obj

    def get_attr(self, name):
        # type: (str) -> NamedObject
        obj = getattr(self.obj, name)
        if self.name:
            name = "{}.{}".format(self.name, name)
        return NamedObject(name, obj)


def import_module(spec):
    # type: (str) -> Optional[Any]
    # Check for empty module name without potentially catching the wrong ValueError.
    if not str:
        return None
    try:
        return importlib.import_module(spec)
    except ImportError:
        return None


def import_longest_module(spec):
    # type: (str) -> Tuple[Optional[NamedObject], Optional[str]]
    """Imports the deepest possible module given a dot-separated
    Python name.

    If no module could be imported, None is returned.

    If there are any parts left then they are returned as a string,
    otherwise None.
    """
    parts = spec.split(".")

    for seq in reversed(list(sequences(parts))):
        last = import_module(".".join(seq))
        if last is not None:
            break
    else:
        return None, spec

    leftover = ".".join(parts[len(seq) :])
    obj = NamedObject(".".join(parts[: len(seq)]), last)
    if leftover:
        return obj, leftover
    return obj, None


def get_longest_attribute(o, spec):
    # type: (NamedObject, str) -> Tuple[NamedObject, Optional[str]]
    parts = spec.split(".")

    for i, part in enumerate(parts):
        try:
            o = o.get_attr(part)
        except AttributeError:
            return o, ".".join(parts[i:])

    return o, None


def package_autocomplete_names(package=None):
    # type: (Any) -> Iterator[str]
    path = None  # type: Optional[str]
    prefix = ""
    if package is not None:
        path = package.__path__
        prefix = "{}.".format(package.__name__)

    for _, name, is_pkg in iter_modules(path):
        module_name = "{}{}".format(prefix, name)
        yield module_name


def children_autocomplete_names(obj):
    # type: (NamedObject) -> Iterable[str]
    """Given a name, get the available children.

    Children can be:
    1. attributes (for a module)
    2. members and contained modules
    (for a package).
    """
    names = []

    if inspect.isclass(obj.obj) or inspect.ismodule(obj.obj):
        for name in dir(obj.obj):
            try:
                attr = obj.get_attr(name)
            except AttributeError:
                # In case someone overrides __dir__ poorly, we shouldn't crash.
                pass
            else:
                # Exclude the __class__ attribute so we don't show it unnecessarily.
                if name != "__class__" and inspect.isclass(attr.obj):
                    names.append(attr.name)

    if hasattr(obj.obj, "__path__"):
        names.extend(package_autocomplete_names(obj.obj))

    return names


def autocomplete(current):
    # type: (str) -> List[str]
    """
    Given the current input, retrieve the useful autocomplete entries.

    Useful autocomplete entries are based on the behavior of `help`:

    1. `help` on a module shows its contents recursively, so we should try to
       autocomplete available module names
    2. `help` on a nested class may show more details than it would otherwise, so we
       should try to autocomplete class names that exist in a module or class
    3. `help` on a class will already show documentation for methods, so no need to
       autocomplete those - users can just use the class and then search in their
       pager for the method. This also avoids displaying too much output (due to
       dunder methods).

    If the user input ends with `.`, then assume that they are trying to get
    available entities within the entity identified by the text before `.`.
    """
    # Whether to retrieve all members of the provided entity (vs doing a match based
    # on prefix for attributes).
    get_members = current.endswith(".")
    if get_members:
        current = current[:-1]

    # Whether the initial input was fully qualified, where we wouldn't want to output
    # sibling matches.
    fully_qualified = get_members

    if get_members or "." in current:
        context, leftover = import_longest_module(current)
        if context is None:
            # No matching modules found.
            return []

        if leftover is not None:
            context, leftover = get_longest_attribute(context, leftover)

        if fully_qualified and leftover is not None:
            # The user input a fully-qualified name, but we weren't able to locate a
            # matching context.
            return []

        get_members = get_members or leftover is not None

        if not get_members:
            return [context.name]
        options = children_autocomplete_names(context)
    else:
        options = list(package_autocomplete_names())
        # Include builtins
        options.extend(name for name in dir(builtins) if not name.startswith("__"))

    return sorted(m for m in options if m.startswith(current))


def autocomplete_bash():
    # type: () -> str
    """User input may be (cursor indicated with pipe):

    1. hlp | -> all builtins/modules
    2. hlp h| -> entities starting with "h"
    3. hlp http.| -> entities in http and prefix with http.
    4. hlp http | -> entities in http and do not prefix
    5. hlp http client.| -> entities in http.client and prefix with client.
    """
    comp_cword = int(os.environ["COMP_CWORD"])
    # Index into our command arguments.
    arg_index = comp_cword - 1
    comp_words_text = os.environ["COMP_WORDS"]
    comp_words = shlex.split(comp_words_text)
    args = comp_words[1 : comp_cword + 1]

    query = ".".join(args)
    at_top_level = len(query) == 0

    # Doing tab completion after already passing some arguments.
    get_members = arg_index == len(args)

    # Get members of context un
    if get_members and not at_top_level:
        query = "{}.".format(query)

    completions = autocomplete(query)

    # All components up to the query string.
    to_strip = len(".".join(args[:arg_index]))
    if to_strip:
        # And a trailing period.
        to_strip += 1

    last_names = [name[to_strip:] for name in completions if not name.endswith(".")]
    # Thankfully Python identifiers are well-behaved, so we don't need to worry
    # about quoting the result.
    return " ".join(last_names)


autocomplete_scripts = {
    "bash": """
        _hlp_completion() {
            _hlp_completion_result="$(
                COMP_WORDS="${COMP_WORDS[*]}" \\
                COMP_CWORD="$COMP_CWORD" \\
                "$1" --autocomplete 2>/dev/null
            )"
            COMPREPLY=( $_hlp_completion_result )
        }

        complete -F _hlp_completion hlp
    """
}


def main(input_args=None):
    if input_args is None:
        input_args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Command-line access to Python's built-in 'help' function"
    )
    parser.add_argument(
        "--autocomplete-init", choices=["bash"], help="Output autocomplete code."
    )
    parser.add_argument(
        "--autocomplete",
        action="store_true",
        help="Internal. Output autocomplete choices.",
    )
    parser.add_argument("query", nargs="*")
    args = parser.parse_args(input_args)

    if args.autocomplete:
        print(autocomplete_bash())
        return

    if args.autocomplete_init:
        print(dedent(autocomplete_scripts[args.autocomplete_init]))
        return

    if not args.query:
        parser.error("'query' is required")

    query = ".".join(args.query)
    obj, attr_spec = import_longest_module(query)

    if obj is None:
        # Maybe a builtin, or prints an errors.
        help(query)
        return

    obj = obj.obj

    if attr_spec is not None:
        obj = getattr_recursive(obj, attr_spec.split("."))

    help(obj)
TW_EOF
mkdir -p hlp
cat > hlp/compat.py <<'TW_EOF'
import pkgutil
import sys

from .typing import MYPY_RUNNING

if MYPY_RUNNING:
    from typing import Any, Iterator, Optional, Tuple


PY2 = sys.version_info < (3,)

if PY2:
    import __builtin__ as builtins  # type: ignore
else:
    import builtins as builtins  # type: ignore


if PY2:

    def iter_modules(path=None):
        # type: (Optional[str]) -> Iterator[Tuple[Any, str, bool]]
        return pkgutil.iter_modules(path)


else:

    def iter_modules(path=None):
        # type: (Optional[str]) -> Iterator[Tuple[Any, str, bool]]
        for info in pkgutil.iter_modules(path):
            yield info, info.name, info.ispkg
TW_EOF
