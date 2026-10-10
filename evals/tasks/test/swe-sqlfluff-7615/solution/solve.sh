#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p src/sqlfluff/core/templaters
cat > src/sqlfluff/core/templaters/placeholder.py <<'TW_EOF'
"""Defines the placeholder template."""

import logging
from typing import Any, Optional

import regex

from sqlfluff.core.config import FluffConfig
from sqlfluff.core.errors import SQLTemplaterError
from sqlfluff.core.formatter import FormatterInterface
from sqlfluff.core.helpers.slice import offset_slice
from sqlfluff.core.templaters.base import (
    RawFileSlice,
    RawTemplater,
    TemplatedFile,
    TemplatedFileSlice,
    large_file_check,
)

# Instantiate the templater logger
templater_logger = logging.getLogger("sqlfluff.templater")

KNOWN_STYLES = {
    # e.g. WHERE bla = :name
    "colon": regex.compile(r"(?<![:\w\x5c]):(?P<param_name>\w+)", regex.UNICODE),
    # e.g. SELECT :"column" FROM :table WHERE bla = :'name'
    "colon_optional_quotes": regex.compile(
        r"(?<!:):(?P<quotation>['\"]?)(?P<param_name>[\w_]+)\1", regex.UNICODE
    ),
    # e.g. WHERE bla = table:name - use with caution as more prone to false positives
    "colon_nospaces": regex.compile(r"(?<!:):(?P<param_name>\w+)", regex.UNICODE),
    # e.g. WHERE bla = :2
    "numeric_colon": regex.compile(
        r"(?<![:\w\x5c]):(?P<param_name>\d+)", regex.UNICODE
    ),
    # e.g. WHERE bla = %(name)s
    "pyformat": regex.compile(
        r"(?<![:\w\x5c])%\((?P<param_name>[\w_]+)\)s", regex.UNICODE
    ),
    # e.g. WHERE bla = $name or WHERE bla = ${name}
    "dollar": regex.compile(
        r"(?<![:\w\x5c])\${?(?P<param_name>[\w_]+)}?", regex.UNICODE
    ),
    # e.g. WHERE bla = $name$ (DbUp compatible)
    "dollar_surround": regex.compile(
        r"(?<![:\w\x5c])\$(?P<param_name>[-\w]+)\$", regex.UNICODE
    ),
    # e.g. USE ${flyway:database}.schema_name;
    "flyway_var": regex.compile(r"\${(?P<param_name>\w+[:\w_]+)}", regex.UNICODE),
    # e.g. WHERE bla = ?
    "question_mark": regex.compile(r"(?<![:\w\x5c])\?", regex.UNICODE),
    # e.g. WHERE bla = $3 or WHERE bla = ${3}
    "numeric_dollar": regex.compile(
        r"(?<![:\w\x5c])\${?(?P<param_name>[\d]+)}?", regex.UNICODE
    ),
    # e.g. WHERE bla = %s
    "percent": regex.compile(r"(?<![:\w\x5c])%s", regex.UNICODE),
    # e.g. WHERE bla = &s or WHERE bla = &{s} or USE DATABASE {ENV}_MARKETING
    "ampersand": regex.compile(r"(?<!&)&{?(?P<param_name>[\w]+)}?", regex.UNICODE),
}


class PlaceholderTemplater(RawTemplater):
    """A templater for generic placeholders.

    Different libraries and tools use different styles of placeholders in
    order to escape them when running queries.

    In order to perform parsing of those templated queries, it's necessary to
    replace these placeholders with user-provided values, which is the job
    of this templater.

    See https://www.python.org/dev/peps/pep-0249/#paramstyle for the
    specifications for Python, they cover most cases.

    """

    name = "placeholder"

    def __init__(self, override_context: Optional[dict[str, Any]] = None):
        self.default_context = dict(test_value="__test__")
        self.override_context = override_context or {}

    # copy of the Python templater
    def get_context(
        self,
        fname: Optional[str],
        config: Optional[FluffConfig],
    ) -> dict[str, Any]:
        """Get the templating context from the config."""
        live_context = super().get_context(fname, config)

        if "param_regex" in live_context and "param_style" in live_context:
            raise ValueError(
                "Either param_style or param_regex must be provided, not both"
            )
        if "param_regex" in live_context:
            live_context["__bind_param_regex"] = regex.compile(
                live_context["param_regex"]
            )
        elif "param_style" in live_context:
            param_style = live_context["param_style"]
            if param_style not in KNOWN_STYLES:
                raise ValueError(
                    'Unknown param_style "{}", available are: {}'.format(
                        param_style, list(KNOWN_STYLES.keys())
                    )
                )
            live_context["__bind_param_regex"] = KNOWN_STYLES[param_style]
        else:
            raise ValueError(
                "No param_regex nor param_style was provided to the placeholder "
                "templater!"
            )

        return live_context

    @large_file_check
    def process(
        self,
        *,
        in_str: str,
        fname: str,
        config: Optional[FluffConfig] = None,
        formatter: Optional[FormatterInterface] = None,
    ) -> tuple[TemplatedFile, list[SQLTemplaterError]]:
        """Process a string and return a TemplatedFile.

        Note that the arguments are enforced as keywords
        because Templaters can have differences in their
        `process` method signature.
        A Templater that only supports reading from a file
        would need the following signature:
            process(*, fname, in_str=None, config=None)
        (arguments are swapped)

        Args:
            in_str (:obj:`str`): The input string.
            fname (:obj:`str`, optional): The filename of this string. This is
                mostly for loading config files at runtime.
            config (:obj:`FluffConfig`): A specific config to use for this
                templating operation. Only necessary for some templaters.
            formatter (:obj:`CallbackFormatter`): Optional object for output.

        """
        context = self.get_context(fname, config)
        template_slices = []
        raw_slices = []
        last_pos_raw, last_pos_templated = 0, 0
        out_str = ""

        regex = context["__bind_param_regex"]
        # when the param has no name, use a 1-based index
        param_counter = 1
        for found_param in regex.finditer(in_str):
            span = found_param.span()
            if "param_name" not in found_param.groupdict():
                param_name = str(param_counter)
                param_counter += 1
            else:
                param_name = found_param["param_name"]
            last_literal_length = span[0] - last_pos_raw
            if param_name in context:
                replacement = str(context[param_name])
            else:
                replacement = param_name
            if "quotation" in found_param.groupdict():
                quotation = found_param["quotation"]
                replacement = quotation + replacement + quotation
            # add the literal to the slices
            template_slices.append(
                TemplatedFileSlice(
                    slice_type="literal",
                    source_slice=slice(last_pos_raw, span[0], None),
                    templated_slice=offset_slice(
                        last_pos_templated,
                        last_literal_length,
                    ),
                )
            )
            raw_slices.append(
                RawFileSlice(
                    raw=in_str[last_pos_raw : span[0]],
                    slice_type="literal",
                    source_idx=last_pos_raw,
                )
            )
            out_str += in_str[last_pos_raw : span[0]]
            # add the current replaced element
            start_template_pos = last_pos_templated + last_literal_length
            template_slices.append(
                TemplatedFileSlice(
                    slice_type="templated",
                    source_slice=slice(span[0], span[1]),
                    templated_slice=offset_slice(start_template_pos, len(replacement)),
                )
            )
            raw_slices.append(
                RawFileSlice(
                    raw=in_str[span[0] : span[1]],
                    slice_type="templated",
                    source_idx=span[0],
                )
            )
            out_str += replacement
            # update the indexes
            last_pos_raw = span[1]
            last_pos_templated = start_template_pos + len(replacement)
        # add the last literal, if any
        if len(in_str) > last_pos_raw:
            template_slices.append(
                TemplatedFileSlice(
                    slice_type="literal",
                    source_slice=slice(last_pos_raw, len(in_str)),
                    templated_slice=offset_slice(
                        last_pos_templated,
                        (len(in_str) - last_pos_raw),
                    ),
                )
            )
            raw_slices.append(
                RawFileSlice(
                    raw=in_str[last_pos_raw:],
                    slice_type="literal",
                    source_idx=last_pos_raw,
                )
            )
            out_str += in_str[last_pos_raw:]
        return (
            TemplatedFile(
                # original string
                source_str=in_str,
                # string after all replacements
                templated_str=out_str,
                # filename
                fname=fname,
                # list of TemplatedFileSlice
                sliced_file=template_slices,
                # list of RawFileSlice, same size
                raw_sliced=raw_slices,
            ),
            [],  # violations, always empty
        )
TW_EOF
mkdir -p src/sqlfluff/rules/references
cat > src/sqlfluff/rules/references/RF03.py <<'TW_EOF'
"""Implementation of Rule RF03."""

from collections.abc import Iterator
from typing import Optional

from sqlfluff.core.dialects.common import AliasInfo, ColumnAliasInfo
from sqlfluff.core.parser import IdentifierSegment
from sqlfluff.core.parser.segments import BaseSegment, SymbolSegment
from sqlfluff.core.rules import (
    BaseRule,
    EvalResultType,
    LintFix,
    LintResult,
    RuleContext,
)
from sqlfluff.core.rules.crawlers import SegmentSeekerCrawler
from sqlfluff.dialects.dialect_ansi import ObjectReferenceSegment
from sqlfluff.utils.analysis.query import Query
from sqlfluff.utils.analysis.select import SelectStatementColumnsAndTables

_START_TYPES = ["select_statement", "set_expression", "with_compound_statement"]


class Rule_RF03(BaseRule):
    """Column references should be qualified consistently in single table statements.

    .. note::
        For BigQuery, Hive and Redshift this rule is disabled by default.
        This is due to historical false positives associated with STRUCT data types.
        This default behaviour may be changed in the future.
        The rule can be enabled with the ``force_enable = True`` flag.

    "consistent" will be fixed to "qualified" if inconsistency is found.

    **Anti-pattern**

    In this example, only the reference to ``b`` is qualified.

    .. code-block:: sql

        SELECT
            a,
            foo.b
        FROM foo

    **Best practice**

    Either all column references should be qualified, or all unqualified.

    .. code-block:: sql

        SELECT
            a,
            b
        FROM foo

        -- Also good

        SELECT
            foo.a,
            foo.b
        FROM foo

    """

    name = "references.consistent"
    aliases = ("L028",)
    groups = ("all", "references")
    config_keywords = [
        "single_table_references",
        "force_enable",
    ]
    # If any of the parents would have also triggered the rule, don't fire
    # because they will more accurately process any internal references.
    crawl_behaviour = SegmentSeekerCrawler(set(_START_TYPES), allow_recurse=False)
    _is_struct_dialect = False
    _dialects_with_structs = ["bigquery", "hive", "redshift"]
    # This could be turned into an option
    _fix_inconsistent_to = "qualified"
    is_fix_compatible = True
    single_table_references: str

    def _eval(self, context: RuleContext) -> EvalResultType:
        """Override base class for dialects that use structs, or SELECT aliases."""
        # Config type hints
        self.force_enable: bool
        # Some dialects use structs (e.g. column.field) which look like
        # table references and so incorrectly trigger this rule.
        if (
            context.dialect.name in self._dialects_with_structs
            and not self.force_enable
        ):
            return LintResult()

        if context.dialect.name in self._dialects_with_structs:
            self._is_struct_dialect = True

        query: Query = Query.from_segment(context.segment, dialect=context.dialect)
        visited: set = set()
        # Recursively visit and check each query in the tree.
        return list(self._visit_queries(query, visited))

    def _iter_available_targets(
        self, query: Query, subquery: Optional[Query] = None
    ) -> Iterator[AliasInfo]:
        """Iterate along a list of valid alias targets."""
        for selectable in query.selectables:
            select_info = selectable.select_info
            if select_info:
                for alias in select_info.table_aliases:
                    if subquery and alias.from_expression_element.path_to(
                        subquery.selectables[0].selectable
                    ):
                        # Skip the subquery alias itself
                        continue
                    if (subquery and not alias.object_reference) or alias.ref_str:
                        yield alias

    def _visit_queries(self, query: Query, visited: set) -> Iterator[LintResult]:
        select_info: Optional[SelectStatementColumnsAndTables] = None
        if query.selectables:
            select_info = query.selectables[0].select_info
            # How many table names are visible from here? If more than one then do
            # nothing.
            if select_info and len(select_info.table_aliases) == 1:
                fixable = True
                # :TRICKY: Subqueries in the column list of a SELECT can see tables
                # in the FROM list of the containing query. Thus, count tables at
                # the *parent* query level. Only check if it is a subquery of the
                # parent.
                possible_ref_tables = list(self._iter_available_targets(query))
                if query.parent and query.is_subquery:
                    possible_ref_tables += list(
                        self._iter_available_targets(query.parent, query)
                    )
                if len(possible_ref_tables) > 1:
                    # If more than one table name is visible, check for and report
                    # potential lint warnings, but don't generate fixes, because
                    # fixes are unsafe if there's more than one table visible.
                    fixable = False

                yield from _check_references(
                    select_info.table_aliases,
                    select_info.standalone_aliases,
                    select_info.reference_buffer,
                    select_info.col_aliases,
                    self.single_table_references,
                    self._is_struct_dialect,
                    self._fix_inconsistent_to,
                    fixable,
                )
        children = list(query.children)
        # 'query.children' includes CTEs and "main" queries, but not queries in
        # the "FROM" list. We want to visit those as well.
        if select_info:
            for a in select_info.table_aliases:
                for q in query.crawl_sources(a.from_expression_element, True):
                    if not isinstance(q, Query):
                        continue
                    # Check for previously visited selectables to avoid possible
                    # infinite recursion, e.g.:
                    #   WITH test1 AS (SELECT i + 1, j + 1 FROM test1)
                    #   SELECT * FROM test1;
                    if any(s.selectable in visited for s in q.selectables):
                        continue
                    visited.update(s.selectable for s in q.selectables)
                    children.append(q)
        for child in children:
            yield from self._visit_queries(child, visited)


def _check_references(
    table_aliases: list[AliasInfo],
    standalone_aliases: list[BaseSegment],
    references: list[ObjectReferenceSegment],
    col_aliases: list[ColumnAliasInfo],
    single_table_references: str,
    is_struct_dialect: bool,
    fix_inconsistent_to: Optional[str],
    fixable: bool,
) -> Iterator[LintResult]:
    """Iterate through references and check consistency."""
    # A buffer to keep any violations.
    col_alias_names: list[str] = [c.alias_identifier_name for c in col_aliases]
    table_ref_str: str = table_aliases[0].ref_str
    table_ref_str_source = table_aliases[0].segment
    # Check all the references that we have.
    seen_ref_types: set[str] = set()
    for ref in references:
        this_ref_type: str = ref.qualification()
        # Skip unqualified templated references (e.g., placeholder parameters like
        # :colname that get rendered as bare identifiers by the templater). These
        # are not real column references and should not be qualified or flagged.
        if this_ref_type == "unqualified" and ref.is_templated:
            continue
        if this_ref_type == "qualified" and is_struct_dialect:
            # If this col appears "qualified" check if it is more logically a struct.
            if next(ref.iter_raw_references()).part != table_ref_str:
                this_ref_type = "unqualified"

        lint_res = _validate_one_reference(
            single_table_references,
            ref,
            this_ref_type,
            standalone_aliases,
            table_ref_str,
            table_ref_str_source,
            col_alias_names,
            seen_ref_types,
            fixable,
        )

        seen_ref_types.add(this_ref_type)
        if not lint_res:
            continue

        if fix_inconsistent_to and single_table_references == "consistent":
            # If we found a "consistent" error but we have a fix directive,
            # recurse with a different single_table_references value.
            # This re-check iterates the same references list, so the templated
            # unqualified-reference skip above still applies and intentionally
            # keeps those placeholders out of every consistency pass.
            yield from _check_references(
                table_aliases,
                standalone_aliases,
                references,
                col_aliases,
                # NB vars are passed in a different order here
                single_table_references=fix_inconsistent_to,
                is_struct_dialect=is_struct_dialect,
                fix_inconsistent_to=None,
                fixable=fixable,
            )

        yield lint_res


def _validate_one_reference(
    single_table_references: str,
    ref: ObjectReferenceSegment,
    this_ref_type: str,
    standalone_aliases: list[BaseSegment],
    table_ref_str: str,
    table_ref_str_source: Optional[BaseSegment],
    col_alias_names: list[str],
    seen_ref_types: set[str],
    fixable: bool,
) -> Optional[LintResult]:
    # We skip any unqualified wildcard references (i.e. *). They shouldn't
    # count.
    if not ref.is_qualified() and ref.is_type("wildcard_identifier"):
        return None
    # Oddball case: Column aliases provided via function calls in by
    # FROM or JOIN. References to these don't need to be qualified.
    # Note there could be a table with a column by the same name as
    # this alias, so avoid bogus warnings by just skipping them
    # entirely rather than trying to enforce anything.
    if ref.raw in [a.raw for a in standalone_aliases]:
        return None

    # If the reference is qualified, see that the table is not in the standalone_aliases
    # namely for lambda expressions.
    if ref.is_qualified():
        standalone_alias_raws = [a.raw for a in standalone_aliases]
        for part in ref.extract_possible_references(
            level=ref.ObjectReferenceLevel.TABLE
        ):
            if part.part in standalone_alias_raws:
                return None
        # Also check the leading (first) part of the reference. For multi-part
        # references like `item.taskId.oid` (e.g. in Databricks higher-order
        # functions), the lambda parameter `item` is at the SCHEMA level, not
        # TABLE level. We need to check it against standalone aliases too.
        first_raw_ref = next(ref.iter_raw_references(), None)
        if first_raw_ref and first_raw_ref.part in standalone_alias_raws:
            return None

    # Oddball case: tsql table variables can't be used to qualify references.
    # This appears here as an empty string for table_ref_str.
    if not table_ref_str:
        return None

    # Certain dialects allow use of SELECT alias in WHERE clauses
    if ref.raw in col_alias_names:
        return None

    # Check first for consistency
    if single_table_references == "consistent":
        if seen_ref_types and this_ref_type not in seen_ref_types:
            return LintResult(
                anchor=ref,
                description=f"{this_ref_type.capitalize()} reference "
                f"{ref.raw!r} found in single table select which is "
                "inconsistent with previous references.",
            )
        # Config is consistent, and this reference matches types so far.
        return None

    # Otherwise check for a specified type of referencing.
    # If it's the right kind already, just return.
    if single_table_references == this_ref_type:
        return None

    # If not, it's the wrong type and we should handle it.
    if single_table_references == "unqualified":
        # If unqualified and not fixable, there is no error.
        if not fixable:
            return None
        # If this is qualified we must have a "table", "."" at least
        return LintResult(
            anchor=ref,
            fixes=[LintFix.delete(el) for el in ref.segments[:2]],
            description="{} reference {!r} found in single table select.".format(
                this_ref_type.capitalize(), ref.raw
            ),
        )

    fixes = None
    if fixable:
        fixes = [
            LintFix.create_before(
                ref.segments[0] if len(ref.segments) else ref,
                source=[table_ref_str_source] if table_ref_str_source else None,
                edit_segments=[
                    IdentifierSegment(
                        raw=table_ref_str,
                        type="naked_identifier",
                    ),
                    SymbolSegment(raw=".", type="symbol"),
                ],
            )
        ]
    return LintResult(
        anchor=ref,
        fixes=fixes,
        description="{} reference {!r} found in single table select.".format(
            this_ref_type.capitalize(), ref.raw
        ),
    )
TW_EOF
