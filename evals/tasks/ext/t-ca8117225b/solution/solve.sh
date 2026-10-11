#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p moto/dynamodb
cat > moto/dynamodb/comparisons.py <<'TW_EOF'
import re
from collections import deque, namedtuple
from collections.abc import Iterable
from decimal import Decimal
from typing import Any, Optional, Union

from moto.dynamodb.exceptions import ConditionAttributeIsReservedKeyword
from moto.dynamodb.models.dynamo_type import Item
from moto.dynamodb.parsing.reserved_keywords import ReservedKeywords


def create_condition_expression_parser(
    expr: Optional[str],
    names: Optional[dict[str, str]],
    values: Optional[dict[str, dict[str, str]]],
) -> "ConditionExpressionParser":
    return ConditionExpressionParser(expr, names, values)


def get_filter_expression(
    expr: Optional[str],
    names: Optional[dict[str, str]],
    values: Optional[dict[str, dict[str, str]]],
) -> Union["Op", "Func"]:
    """
    Parse a filter expression into an Op.

    Examples
        expr = 'Id > 5 AND attribute_exists(test) AND Id BETWEEN 5 AND 6 OR length < 6 AND contains(test, 1) AND 5 IN (4,5, 6) OR (Id < 5 AND 5 > Id)'
        expr = 'Id > 5 AND Subs < 7'
    """
    parser = create_condition_expression_parser(expr, names, values)
    return parser.parse()


def get_expected(expected: dict[str, Any]) -> Union["Op", "Func"]:
    """
    Parse a filter expression into an Op.

    Examples
        expr = 'Id > 5 AND attribute_exists(test) AND Id BETWEEN 5 AND 6 OR length < 6 AND contains(test, 1) AND 5 IN (4,5, 6) OR (Id < 5 AND 5 > Id)'
        expr = 'Id > 5 AND Subs < 7'
    """
    ops: dict[str, Any] = {
        "EQ": OpEqual,
        "NE": OpNotEqual,
        "LE": OpLessThanOrEqual,
        "LT": OpLessThan,
        "GE": OpGreaterThanOrEqual,
        "GT": OpGreaterThan,
        "NOT_NULL": FuncAttrExists,
        "NULL": FuncAttrNotExists,
        "CONTAINS": FuncContains,
        "NOT_CONTAINS": FuncNotContains,
        "BEGINS_WITH": FuncBeginsWith,
        "IN": FuncIn,
        "BETWEEN": FuncBetween,
    }

    # NOTE: Always uses ConditionalOperator=AND
    conditions: list[Union[Op, Func]] = []
    for key, cond in expected.items():
        path = AttributePath([key])
        if "Exists" in cond:
            if cond["Exists"]:
                conditions.append(FuncAttrExists(path))
            else:
                conditions.append(FuncAttrNotExists(path))
        elif "Value" in cond:
            conditions.append(OpEqual(path, AttributeValue(cond["Value"])))
        elif "ComparisonOperator" in cond:
            operator_name = cond["ComparisonOperator"]
            values = [AttributeValue(v) for v in cond.get("AttributeValueList", [])]
            OpClass = ops[operator_name]
            conditions.append(OpClass(path, *values))

    # NOTE: Ignore ConditionalOperator
    ConditionalOp = OpAnd
    if conditions:
        output = conditions[0]
        for condition in conditions[1:]:
            output = ConditionalOp(output, condition)
    else:
        return OpDefault(None, None)  # type: ignore[arg-type]

    return output


class Op:
    """
    Base class for a FilterExpression operator
    """

    OP = ""

    def __init__(
        self, lhs: Union["Func", "Op", "Operand"], rhs: Union["Func", "Op", "Operand"]
    ):
        self.lhs = lhs
        self.rhs = rhs

    def expr(self, item: Optional[Item]) -> bool:
        raise NotImplementedError(f"Expr not defined for {type(self)}")

    def __repr__(self) -> str:
        return f"({self.lhs} {self.OP} {self.rhs})"


# TODO add tests for all of these

EQ_FUNCTION = lambda item_value, test_value: item_value == test_value  # noqa
NE_FUNCTION = lambda item_value, test_value: item_value != test_value  # noqa
LE_FUNCTION = lambda item_value, test_value: item_value <= test_value  # noqa
LT_FUNCTION = lambda item_value, test_value: item_value < test_value  # noqa
GE_FUNCTION = lambda item_value, test_value: item_value >= test_value  # noqa
GT_FUNCTION = lambda item_value, test_value: item_value > test_value  # noqa

COMPARISON_FUNCS = {
    "EQ": EQ_FUNCTION,
    "=": EQ_FUNCTION,
    "NE": NE_FUNCTION,
    "!=": NE_FUNCTION,
    "LE": LE_FUNCTION,
    "<=": LE_FUNCTION,
    "LT": LT_FUNCTION,
    "<": LT_FUNCTION,
    "GE": GE_FUNCTION,
    ">=": GE_FUNCTION,
    "GT": GT_FUNCTION,
    ">": GT_FUNCTION,
    # NULL means the value should not exist at all
    "NULL": lambda item_value: False,
    # NOT_NULL means the value merely has to exist, and values of None are valid
    "NOT_NULL": lambda item_value: True,
    "CONTAINS": lambda item_value, test_value: test_value in item_value,
    "NOT_CONTAINS": lambda item_value, test_value: test_value not in item_value,
    "BEGINS_WITH": lambda item_value, test_value: item_value.startswith(test_value),
    "IN": lambda item_value, *test_values: item_value in test_values,
    "BETWEEN": lambda item_value, lower_test_value, upper_test_value: lower_test_value
    <= item_value
    <= upper_test_value,
}


def get_comparison_func(range_comparison: str) -> Any:
    return COMPARISON_FUNCS.get(range_comparison)


class RecursionStopIteration(StopIteration):
    pass


class ConditionExpressionParser:
    def __init__(
        self,
        condition_expression: Optional[str],
        expression_attribute_names: Optional[dict[str, str]],
        expression_attribute_values: Optional[dict[str, dict[str, str]]],
    ):
        self.condition_expression = condition_expression
        self.expression_attribute_names = expression_attribute_names
        self.expression_attribute_values = expression_attribute_values

        self.expr_attr_names_found: list[str] = []
        self.expr_attr_values_found: list[str] = []

    def parse(self) -> Union[Op, "Func"]:
        """Returns a syntax tree for the expression.

        The tree, and all of the nodes in the tree are a tuple of
        - kind: str
        - children/value:
            list of nodes for parent nodes
            value for leaf nodes

        Raises ValueError if the condition expression is invalid
        Raises KeyError if expression attribute names/values are invalid

        Here are the types of nodes that can be returned.
        The types of child nodes are denoted with a colon (:).
        An arbitrary number of children is denoted with ...

        Condition:
            ('OR', [lhs : Condition, rhs : Condition])
            ('AND', [lhs: Condition, rhs: Condition])
            ('NOT', [argument: Condition])
            ('PARENTHESES', [argument: Condition])
            ('FUNCTION', [('LITERAL', function_name: str), argument: Operand, ...])
            ('BETWEEN', [query: Operand, low: Operand, high: Operand])
            ('IN', [query: Operand, possible_value: Operand, ...])
            ('COMPARISON', [lhs: Operand, ('LITERAL', comparator: str), rhs: Operand])

        Operand:
            ('EXPRESSION_ATTRIBUTE_VALUE', value: dict, e.g. {'S': 'foobar'})
            ('PATH', [('LITERAL', path_element: str), ...])
            NOTE: Expression attribute names will be expanded
            ('FUNCTION', [('LITERAL', 'size'), argument: Operand])

        Literal:
            ('LITERAL', value: str)

        """
        if not self.condition_expression:
            return OpDefault(None, None)  # type: ignore[arg-type]
        nodes = self._lex_condition_expression()
        nodes = self._parse_paths(nodes)
        # NOTE: The docs say that functions should be parsed after
        # IN, BETWEEN, and comparisons like <=.
        # However, these expressions are invalid as function arguments,
        # so it is okay to parse functions first. This needs to be done
        # to interpret size() correctly as an operand.
        nodes = self._apply_functions(nodes)
        nodes = self._apply_comparator(nodes)
        nodes = self._apply_in(nodes)
        nodes = self._apply_between(nodes)
        nodes = self._apply_parens_and_booleans(nodes)
        node = nodes[0]

        self.expr_attr_names_found.extend(self._find_literals(node))
        self.expr_attr_values_found.extend(self._find_expr_attr_values(node))

        op = self._make_op_condition(node)
        return op

    class Kind:
        """Enum defining types of nodes in the syntax tree."""

        # Condition nodes
        # ---------------
        OR = "OR"
        AND = "AND"
        NOT = "NOT"
        PARENTHESES = "PARENTHESES"
        FUNCTION = "FUNCTION"
        BETWEEN = "BETWEEN"
        IN = "IN"
        COMPARISON = "COMPARISON"

        # Operand nodes
        # -------------
        EXPRESSION_ATTRIBUTE_VALUE = "EXPRESSION_ATTRIBUTE_VALUE"
        PATH = "PATH"

        # Literal nodes
        # --------------
        LITERAL = "LITERAL"

    class Nonterminal:
        """Enum defining nonterminals for productions."""

        CONDITION = "CONDITION"
        OPERAND = "OPERAND"
        COMPARATOR = "COMPARATOR"
        FUNCTION_NAME = "FUNCTION_NAME"
        IDENTIFIER = "IDENTIFIER"
        AND = "AND"
        OR = "OR"
        NOT = "NOT"
        BETWEEN = "BETWEEN"
        IN = "IN"
        COMMA = "COMMA"
        LEFT_PAREN = "LEFT_PAREN"
        RIGHT_PAREN = "RIGHT_PAREN"
        WHITESPACE = "WHITESPACE"

    Node = namedtuple("Node", ["nonterminal", "kind", "text", "value", "children"])

    @classmethod
    def _find_literals(cls, parent: Node) -> list[str]:  # type: ignore
        literals: list[str] = []
        if (
            parent.kind == cls.Kind.LITERAL
            and parent.nonterminal == cls.Nonterminal.IDENTIFIER
        ):
            literals.append(parent.text)
        else:
            for child in parent.children:
                literals.extend(cls._find_literals(child))
        return literals

    @classmethod
    def _find_expr_attr_values(cls, parent: Node) -> list[str]:  # type: ignore
        literals: list[str] = []
        if parent.kind == ConditionExpressionParser.Kind.EXPRESSION_ATTRIBUTE_VALUE:
            literals.append(parent.text)
        else:
            for child in parent.children:
                literals.extend(cls._find_expr_attr_values(child))
        return literals

    @classmethod
    def raise_exception_if_keyword(cls, attribute: str) -> None:
        if attribute.upper() in ReservedKeywords.get_reserved_keywords():
            raise ConditionAttributeIsReservedKeyword(attribute)

    def _lex_condition_expression(self) -> deque[Node]:
        nodes: deque[ConditionExpressionParser.Node] = deque()
        remaining_expression = self.condition_expression
        while remaining_expression:
            node, remaining_expression = self._lex_one_node(remaining_expression)
            if node.nonterminal == self.Nonterminal.WHITESPACE:
                continue
            nodes.append(node)
        return nodes

    def _lex_one_node(self, remaining_expression: str) -> tuple[Node, str]:
        # TODO: Handle indexing like [1]
        attribute_regex = r"(:|#)?[A-z0-9\-_]+"
        patterns = [
            (self.Nonterminal.WHITESPACE, re.compile(r"^ +")),
            (
                self.Nonterminal.COMPARATOR,
                re.compile(
                    "^("
                    # Put long expressions first for greedy matching
                    "<>|"
                    "<=|"
                    ">=|"
                    "=|"
                    "<|"
                    ">)"
                ),
            ),
            (
                self.Nonterminal.OPERAND,
                re.compile(rf"^{attribute_regex}(\.{attribute_regex}|\[[0-9]\])*"),
            ),
            (self.Nonterminal.COMMA, re.compile(r"^,")),
            (self.Nonterminal.LEFT_PAREN, re.compile(r"^\(")),
            (self.Nonterminal.RIGHT_PAREN, re.compile(r"^\)")),
        ]

        for nonterminal, pattern in patterns:
            match = pattern.match(remaining_expression)
            if match:
                match_text = match.group()
                node = self.Node(
                    nonterminal=nonterminal,
                    kind=self.Kind.LITERAL,
                    text=match_text,
                    value=match_text,
                    children=[],
                )

                remaining_expression = remaining_expression[len(match_text) :]

                return node, remaining_expression
        raise ValueError(f"Cannot parse condition starting at:{remaining_expression}")

    def _parse_paths(self, nodes: deque[Node]) -> deque[Node]:
        output: deque[ConditionExpressionParser.Node] = deque()

        while nodes:
            node = nodes.popleft()

            if node.nonterminal == self.Nonterminal.OPERAND:
                path = node.value.replace("[", ".[").split(".")
                children = [self._parse_path_element(name) for name in path]
                if len(children) == 1:
                    child = children[0]
                    if child.nonterminal != self.Nonterminal.IDENTIFIER:
                        output.append(child)
                        continue
                else:
                    for child in children:
                        self._assert(
                            child.nonterminal == self.Nonterminal.IDENTIFIER,
                            f"Cannot use {child.text} in path",
                            [node],
                        )
                output.append(
                    self.Node(
                        nonterminal=self.Nonterminal.OPERAND,
                        kind=self.Kind.PATH,
                        text=node.text,
                        value=None,
                        children=children,
                    )
                )
            else:
                output.append(node)
        return output

    def _parse_path_element(self, name: str) -> Node:
        reserved = {
            "and": self.Nonterminal.AND,
            "or": self.Nonterminal.OR,
            "in": self.Nonterminal.IN,
            "between": self.Nonterminal.BETWEEN,
            "not": self.Nonterminal.NOT,
        }

        functions = {
            "attribute_exists",
            "attribute_not_exists",
            "attribute_type",
            "begins_with",
            "contains",
            "size",
        }

        if name.lower() in reserved:
            # e.g. AND
            nonterminal = reserved[name.lower()]
            return self.Node(
                nonterminal=nonterminal,
                kind=self.Kind.LITERAL,
                text=name,
                value=name,
                children=[],
            )
        elif name in functions:
            # e.g. attribute_exists
            return self.Node(
                nonterminal=self.Nonterminal.FUNCTION_NAME,
                kind=self.Kind.LITERAL,
                text=name,
                value=name,
                children=[],
            )
        elif name.startswith(":"):
            # e.g. :value0
            return self.Node(
                nonterminal=self.Nonterminal.OPERAND,
                kind=self.Kind.EXPRESSION_ATTRIBUTE_VALUE,
                text=name,
                value=self._lookup_expression_attribute_value(name),
                children=[],
            )
        elif name.startswith("#"):
            # e.g. #name0
            return self.Node(
                nonterminal=self.Nonterminal.IDENTIFIER,
                kind=self.Kind.LITERAL,
                text=name,
                value=self._lookup_expression_attribute_name(name),
                children=[],
            )
        elif name.startswith("["):
            # e.g. [123]
            if not name.endswith("]"):  # pragma: no cover
                raise ValueError(f"Bad path element {name}")
            return self.Node(
                nonterminal=self.Nonterminal.IDENTIFIER,
                kind=self.Kind.LITERAL,
                text=name,
                value=int(name[1:-1]),
                children=[],
            )
        else:
            # e.g. ItemId
            self.raise_exception_if_keyword(name)
            return self.Node(
                nonterminal=self.Nonterminal.IDENTIFIER,
                kind=self.Kind.LITERAL,
                text=name,
                value=name,
                children=[],
            )

    def _lookup_expression_attribute_value(self, name: str) -> dict[str, str]:
        return self.expression_attribute_values[name]  # type: ignore[index]

    def _lookup_expression_attribute_name(self, name: str) -> str:
        return self.expression_attribute_names[name]  # type: ignore[index]

    # NOTE: The following constructions are ordered from high precedence to low precedence
    # according to
    # https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.OperatorsAndFunctions.html#Expressions.OperatorsAndFunctions.Precedence
    #
    # = <> < <= > >=
    # IN
    # BETWEEN
    # attribute_exists attribute_not_exists begins_with contains
    # Parentheses
    # NOT
    # AND
    # OR
    #
    # The grammar is taken from
    # https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.OperatorsAndFunctions.html#Expressions.OperatorsAndFunctions.Syntax
    #
    # condition-expression ::=
    #     operand comparator operand
    #     operand BETWEEN operand AND operand
    #     operand IN ( operand (',' operand (, ...) ))
    #     function
    #     condition AND condition
    #     condition OR condition
    #     NOT condition
    #     ( condition )
    #
    # comparator ::=
    #     =
    #     <>
    #     <
    #     <=
    #     >
    #     >=
    #
    # function ::=
    #     attribute_exists (path)
    #     attribute_not_exists (path)
    #     attribute_type (path, type)
    #     begins_with (path, substr)
    #     contains (path, operand)
    #     size (path)

    def _matches(self, nodes: deque[Node], production: list[str]) -> bool:
        """Check if the nodes start with the given production.

        Parameters
        ----------
        nodes: list of Node
        production: list of str
            The name of a Nonterminal, or '*' for anything

        """
        if len(nodes) < len(production):
            return False
        for i in range(len(production)):
            if production[i] == "*":
                continue
            expected = getattr(self.Nonterminal, production[i])
            if nodes[i].nonterminal != expected:
                return False
        return True

    def _apply_comparator(self, nodes: deque[Node]) -> deque[Node]:
        """Apply condition := operand comparator operand."""
        output: deque[ConditionExpressionParser.Node] = deque()

        while nodes:
            if self._matches(nodes, ["*", "COMPARATOR"]):
                self._assert(
                    self._matches(nodes, ["OPERAND", "COMPARATOR", "OPERAND"]),
                    "Bad comparison",
                    list(nodes)[:3],
                )
                lhs = nodes.popleft()
                comparator = nodes.popleft()
                rhs = nodes.popleft()
                nodes.appendleft(
                    self.Node(
                        nonterminal=self.Nonterminal.CONDITION,
                        kind=self.Kind.COMPARISON,
                        text=" ".join([lhs.text, comparator.text, rhs.text]),
                        value=None,
                        children=[lhs, comparator, rhs],
                    )
                )
            else:
                output.append(nodes.popleft())
        return output

    def _apply_in(self, nodes: deque[Node]) -> deque[Node]:
        """Apply condition := operand IN ( operand , ... )."""
        output: deque[ConditionExpressionParser.Node] = deque()
        while nodes:
            if self._matches(nodes, ["*", "IN"]):
                self._assert(
                    self._matches(nodes, ["OPERAND", "IN", "LEFT_PAREN"]),
                    "Bad IN expression",
                    list(nodes)[:3],
                )
                lhs = nodes.popleft()
                in_node = nodes.popleft()
                left_paren = nodes.popleft()
                all_children = [lhs, in_node, left_paren]
                rhs = []
                while True:
                    if self._matches(nodes, ["OPERAND", "COMMA"]):
                        operand = nodes.popleft()
                        separator = nodes.popleft()
                        all_children += [operand, separator]
                        rhs.append(operand)
                    elif self._matches(nodes, ["OPERAND", "RIGHT_PAREN"]):
                        operand = nodes.popleft()
                        separator = nodes.popleft()
                        all_children += [operand, separator]
                        rhs.append(operand)
                        break  # Close
                    else:
                        self._assert(False, "Bad IN expression starting at", nodes)
                nodes.appendleft(
                    self.Node(
                        nonterminal=self.Nonterminal.CONDITION,
                        kind=self.Kind.IN,
                        text=" ".join([t.text for t in all_children]),
                        value=None,
                        children=[lhs] + rhs,
                    )
                )
            else:
                output.append(nodes.popleft())
        return output

    def _apply_between(self, nodes: deque[Node]) -> deque[Node]:
        """Apply condition := operand BETWEEN operand AND operand."""
        output: deque[ConditionExpressionParser.Node] = deque()
        while nodes:
            if self._matches(nodes, ["*", "BETWEEN"]):
                self._assert(
                    self._matches(
                        nodes, ["OPERAND", "BETWEEN", "OPERAND", "AND", "OPERAND"]
                    ),
                    "Bad BETWEEN expression",
                    list(nodes)[:5],
                )
                lhs = nodes.popleft()
                between_node = nodes.popleft()
                low = nodes.popleft()
                and_node = nodes.popleft()
                high = nodes.popleft()
                all_children = [lhs, between_node, low, and_node, high]
                nodes.appendleft(
                    self.Node(
                        nonterminal=self.Nonterminal.CONDITION,
                        kind=self.Kind.BETWEEN,
                        text=" ".join([t.text for t in all_children]),
                        value=None,
                        children=[lhs, low, high],
                    )
                )
            else:
                output.append(nodes.popleft())
        return output

    def _apply_functions(self, nodes: deque[Node]) -> deque[Node]:
        """Apply condition := function_name (operand , ...)."""
        output: deque[ConditionExpressionParser.Node] = deque()
        either_kind = {self.Kind.PATH, self.Kind.EXPRESSION_ATTRIBUTE_VALUE}
        expected_argument_kind_map = {
            "attribute_exists": [{self.Kind.PATH}],
            "attribute_not_exists": [{self.Kind.PATH}],
            "attribute_type": [either_kind, {self.Kind.EXPRESSION_ATTRIBUTE_VALUE}],
            "begins_with": [either_kind, either_kind],
            "contains": [either_kind, either_kind],
            "size": [{self.Kind.PATH}],
        }
        while nodes:
            if self._matches(nodes, ["FUNCTION_NAME"]):
                self._assert(
                    self._matches(
                        nodes, ["FUNCTION_NAME", "LEFT_PAREN", "OPERAND", "*"]
                    ),
                    "Bad function expression at",
                    list(nodes)[:4],
                )
                function_name = nodes.popleft()
                left_paren = nodes.popleft()
                all_children = [function_name, left_paren]
                arguments = []
                while True:
                    if self._matches(nodes, ["OPERAND", "COMMA"]):
                        operand = nodes.popleft()
                        separator = nodes.popleft()
                        all_children += [operand, separator]
                        arguments.append(operand)
                    elif self._matches(nodes, ["OPERAND", "RIGHT_PAREN"]):
                        operand = nodes.popleft()
                        separator = nodes.popleft()
                        all_children += [operand, separator]
                        arguments.append(operand)
                        break  # Close paren
                    else:
                        self._assert(
                            False,
                            "Bad function expression",
                            all_children + list(nodes)[:2],
                        )
                expected_kinds = expected_argument_kind_map[function_name.value]
                self._assert(
                    len(arguments) == len(expected_kinds),
                    "Wrong number of arguments in",
                    all_children,
                )
                for i in range(len(expected_kinds)):
                    self._assert(
                        arguments[i].kind in expected_kinds[i],
                        f"Wrong type for argument {i} in",
                        all_children,
                    )
                if function_name.value == "size":
                    nonterminal = self.Nonterminal.OPERAND
                else:
                    nonterminal = self.Nonterminal.CONDITION
                nodes.appendleft(
                    self.Node(
                        nonterminal=nonterminal,
                        kind=self.Kind.FUNCTION,
                        text=" ".join([t.text for t in all_children]),
                        value=None,
                        children=[function_name] + arguments,
                    )
                )
            else:
                output.append(nodes.popleft())
        return output

    def _apply_parens_and_booleans(
        self, nodes: deque[Node], left_paren: Any = None
    ) -> deque[Node]:
        """Apply condition := ( condition ) and booleans."""
        output: deque[ConditionExpressionParser.Node] = deque()
        while nodes:
            if self._matches(nodes, ["LEFT_PAREN"]):
                parsed = self._apply_parens_and_booleans(
                    nodes, left_paren=nodes.popleft()
                )
                self._assert(len(parsed) >= 1, "Failed to close parentheses at", nodes)
                parens = parsed.popleft()
                self._assert(
                    parens.kind == self.Kind.PARENTHESES,
                    "Failed to close parentheses at",
                    nodes,
                )
                output.append(parens)
                nodes = parsed
            elif self._matches(nodes, ["RIGHT_PAREN"]):
                self._assert(left_paren is not None, "Unmatched ) at", nodes)
                close_paren = nodes.popleft()
                children = self._apply_booleans(output)
                all_children = [left_paren] + list(children) + [close_paren]
                return deque(
                    [
                        self.Node(
                            nonterminal=self.Nonterminal.CONDITION,
                            kind=self.Kind.PARENTHESES,
                            text=" ".join([t.text for t in all_children]),
                            value=None,
                            children=list(children),
                        )
                    ]
                    + list(nodes)
                )
            else:
                output.append(nodes.popleft())

        self._assert(left_paren is None, "Unmatched ( at", list(output))
        return self._apply_booleans(output)

    def _apply_booleans(self, nodes: deque[Node]) -> deque[Node]:
        """Apply and, or, and not constructions."""
        nodes = self._apply_not(nodes)
        nodes = self._apply_and(nodes)
        nodes = self._apply_or(nodes)
        # The expression should reduce to a single condition
        self._assert(len(nodes) == 1, "Unexpected expression at", list(nodes)[1:])
        self._assert(
            nodes[0].nonterminal == self.Nonterminal.CONDITION,
            "Incomplete condition",
            nodes,
        )
        return nodes

    def _apply_not(self, nodes: deque[Node]) -> deque[Node]:
        """Apply condition := NOT condition."""
        output: deque[ConditionExpressionParser.Node] = deque()
        while nodes:
            if self._matches(nodes, ["NOT"]):
                self._assert(
                    self._matches(nodes, ["NOT", "CONDITION"]),
                    "Bad NOT expression",
                    list(nodes)[:2],
                )
                not_node = nodes.popleft()
                child = nodes.popleft()
                nodes.appendleft(
                    self.Node(
                        nonterminal=self.Nonterminal.CONDITION,
                        kind=self.Kind.NOT,
                        text=" ".join([not_node.text, child.text]),
                        value=None,
                        children=[child],
                    )
                )
            else:
                output.append(nodes.popleft())

        return output

    def _apply_and(self, nodes: deque[Node]) -> deque[Node]:
        """Apply condition := condition AND condition."""
        output: deque[ConditionExpressionParser.Node] = deque()
        while nodes:
            if self._matches(nodes, ["*", "AND"]):
                self._assert(
                    self._matches(nodes, ["CONDITION", "AND", "CONDITION"]),
                    "Bad AND expression",
                    list(nodes)[:3],
                )
                lhs = nodes.popleft()
                and_node = nodes.popleft()
                rhs = nodes.popleft()
                all_children = [lhs, and_node, rhs]
                nodes.appendleft(
                    self.Node(
                        nonterminal=self.Nonterminal.CONDITION,
                        kind=self.Kind.AND,
                        text=" ".join([t.text for t in all_children]),
                        value=None,
                        children=[lhs, rhs],
                    )
                )
            else:
                output.append(nodes.popleft())

        return output

    def _apply_or(self, nodes: deque[Node]) -> deque[Node]:
        """Apply condition := condition OR condition."""
        output: deque[ConditionExpressionParser.Node] = deque()
        while nodes:
            if self._matches(nodes, ["*", "OR"]):
                self._assert(
                    self._matches(nodes, ["CONDITION", "OR", "CONDITION"]),
                    "Bad OR expression",
                    list(nodes)[:3],
                )
                lhs = nodes.popleft()
                or_node = nodes.popleft()
                rhs = nodes.popleft()
                all_children = [lhs, or_node, rhs]
                nodes.appendleft(
                    self.Node(
                        nonterminal=self.Nonterminal.CONDITION,
                        kind=self.Kind.OR,
                        text=" ".join([t.text for t in all_children]),
                        value=None,
                        children=[lhs, rhs],
                    )
                )
            else:
                output.append(nodes.popleft())

        return output

    def _make_operand(self, node: Node) -> "Operand":
        if node.kind == self.Kind.PATH:
            return AttributePath([child.value for child in node.children])
        elif node.kind == self.Kind.EXPRESSION_ATTRIBUTE_VALUE:
            return AttributeValue(node.value)
        elif node.kind == self.Kind.FUNCTION:
            # size()
            function_node = node.children[0]
            arguments = node.children[1:]
            function_name = function_node.value
            arguments = [self._make_operand(arg) for arg in arguments]
            return FUNC_CLASS[function_name](*arguments)
        else:  # pragma: no cover
            raise ValueError(f"Unknown operand: {node}")

    def _make_op_condition(self, node: Node) -> Union["Func", Op]:
        if node.kind == self.Kind.OR:
            lhs, rhs = node.children
            return OpOr(self._make_op_condition(lhs), self._make_op_condition(rhs))
        elif node.kind == self.Kind.AND:
            lhs, rhs = node.children
            return OpAnd(self._make_op_condition(lhs), self._make_op_condition(rhs))
        elif node.kind == self.Kind.NOT:
            (child,) = node.children
            return OpNot(self._make_op_condition(child))
        elif node.kind == self.Kind.PARENTHESES:
            (child,) = node.children
            return self._make_op_condition(child)
        elif node.kind == self.Kind.FUNCTION:
            function_node = node.children[0]
            arguments = node.children[1:]
            function_name = function_node.value
            arguments = [self._make_operand(arg) for arg in arguments]
            return FUNC_CLASS[function_name](*arguments)
        elif node.kind == self.Kind.BETWEEN:
            query, low, high = node.children
            return FuncBetween(
                self._make_operand(query),
                self._make_operand(low),
                self._make_operand(high),
            )
        elif node.kind == self.Kind.IN:
            query = node.children[0]
            possible_values = node.children[1:]
            query = self._make_operand(query)
            possible_values = [self._make_operand(v) for v in possible_values]
            return FuncIn(query, *possible_values)
        elif node.kind == self.Kind.COMPARISON:
            lhs, comparator, rhs = node.children
            return COMPARATOR_CLASS[comparator.value](
                self._make_operand(lhs), self._make_operand(rhs)
            )
        else:  # pragma: no cover
            raise ValueError(f"Unknown expression node kind {node.kind}")

    def _assert(self, condition: bool, message: str, nodes: Iterable[Node]) -> None:
        if not condition:
            raise ValueError(message + " " + " ".join([t.text for t in nodes]))


class Operand:
    def expr(self, item: Optional[Item]) -> Any:
        raise NotImplementedError

    def get_type(self, item: Optional[Item]) -> Optional[str]:
        raise NotImplementedError


class AttributePath(Operand):
    def __init__(self, path: list[Any]):
        """Initialize the AttributePath.

        Parameters
        ----------
        path: list of int/str

        """
        assert len(path) >= 1
        self.path = path

    def _get_attr(self, item: Optional[Item]) -> Any:
        if item is None:
            return None

        base = self.path[0]
        if base not in item.attrs:
            return None
        attr = item.attrs[base]

        for name in self.path[1:]:
            attr = attr.child_attr(name)
            if attr is None:
                return None

        return attr

    def expr(self, item: Optional[Item]) -> Any:
        attr = self._get_attr(item)
        if attr is None:
            return None
        else:
            return attr.cast_value

    def get_type(self, item: Optional[Item]) -> Optional[str]:
        attr = self._get_attr(item)
        if attr is None:
            return None
        else:
            return attr.type

    def __repr__(self) -> str:
        return ".".join(self.path)


class AttributeValue(Operand):
    def __init__(self, value: dict[str, Any]):
        """Initialize the AttributePath.

        Parameters
        ----------
        value: dict
            e.g. {'N': '1.234'}

        """
        self.type = list(value.keys())[0]
        self.value = value[self.type]

    def expr(self, item: Optional[Item]) -> Any:
        if self.type == "N":
            return Decimal(self.value)
        elif self.type in ["SS", "NS", "BS"]:
            sub_type = self.type[0]
            return {AttributeValue({sub_type: v}).expr(item) for v in self.value}
        elif self.type == "L":
            return [AttributeValue(v).expr(item) for v in self.value]
        elif self.type == "M":
            return {k: AttributeValue(v).expr(item) for k, v in self.value.items()}
        elif self.type == "NULL":
            return None
        else:
            return self.value
        return self.value

    def get_type(self, item: Optional[Item]) -> str:
        return self.type

    def __repr__(self) -> str:
        return repr(self.value)


class OpDefault(Op):
    OP = "NONE"

    def expr(self, item: Optional[Item]) -> bool:
        """If no condition is specified, always True."""
        return True


class OpNot(Op):
    OP = "NOT"

    def __init__(self, lhs: Union["Func", Op]):
        super().__init__(lhs, None)  # type: ignore[arg-type]

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        return not lhs

    def __str__(self) -> str:
        return f"({self.OP} {self.lhs})"


class OpAnd(Op):
    OP = "AND"

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        return lhs and self.rhs.expr(item)


class OpLessThan(Op):
    OP = "<"

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        rhs = self.rhs.expr(item)
        # In python3 None is not a valid comparator when using < or > so must be handled specially
        if lhs is not None and rhs is not None:
            return lhs < rhs
        else:
            return False


class OpGreaterThan(Op):
    OP = ">"

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        rhs = self.rhs.expr(item)
        # In python3 None is not a valid comparator when using < or > so must be handled specially
        if lhs is not None and rhs is not None:
            return lhs > rhs
        else:
            return False


class OpEqual(Op):
    OP = "="

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        rhs = self.rhs.expr(item)
        return lhs == rhs


class OpNotEqual(Op):
    OP = "<>"

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        rhs = self.rhs.expr(item)
        return lhs != rhs


class OpLessThanOrEqual(Op):
    OP = "<="

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        rhs = self.rhs.expr(item)
        # In python3 None is not a valid comparator when using < or > so must be handled specially
        if lhs is not None and rhs is not None:
            return lhs <= rhs
        else:
            return False


class OpGreaterThanOrEqual(Op):
    OP = ">="

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        rhs = self.rhs.expr(item)
        # In python3 None is not a valid comparator when using < or > so must be handled specially
        if lhs is not None and rhs is not None:
            return lhs >= rhs
        else:
            return False


class OpOr(Op):
    OP = "OR"

    def expr(self, item: Optional[Item]) -> bool:
        lhs = self.lhs.expr(item)
        return lhs or self.rhs.expr(item)


class Func:
    """
    Base class for a FilterExpression function
    """

    FUNC = "Unknown"

    def __init__(self, *arguments: Any):
        self.arguments = arguments

    def expr(self, item: Optional[Item]) -> bool:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.FUNC}({' '.join([repr(arg) for arg in self.arguments])})"


class FuncAttrExists(Func):
    FUNC = "attribute_exists"

    def __init__(self, attribute: Operand):
        self.attr = attribute
        super().__init__(attribute)

    def expr(self, item: Optional[Item]) -> bool:
        return self.attr.get_type(item) is not None


def FuncAttrNotExists(attribute: Operand) -> Any:
    return OpNot(FuncAttrExists(attribute))


class FuncAttrType(Func):
    FUNC = "attribute_type"

    def __init__(self, attribute: Operand, _type: Func):
        self.attr = attribute
        self.type = _type
        super().__init__(attribute, _type)

    def expr(self, item: Optional[Item]) -> bool:
        return self.attr.get_type(item) == self.type.expr(item)  # type: ignore[comparison-overlap]


class FuncBeginsWith(Func):
    FUNC = "begins_with"

    def __init__(self, attribute: Operand, substr: Operand):
        self.attr = attribute
        self.substr = substr
        super().__init__(attribute, substr)

    def expr(self, item: Optional[Item]) -> bool:
        if self.attr.get_type(item) != "S":
            return False
        if self.substr.get_type(item) != "S":
            return False
        return self.attr.expr(item).startswith(self.substr.expr(item))


class FuncContains(Func):
    FUNC = "contains"

    def __init__(self, attribute: Operand, operand: Operand):
        self.attr = attribute
        self.operand = operand
        super().__init__(attribute, operand)

    def expr(self, item: Optional[Item]) -> bool:
        if self.attr.get_type(item) in ("S", "SS", "NS", "BS", "L"):
            try:
                return self.operand.expr(item) in self.attr.expr(item)
            except TypeError:
                return False
        return False


def FuncNotContains(attribute: Operand, operand: Operand) -> OpNot:
    return OpNot(FuncContains(attribute, operand))


class FuncSize(Func):
    FUNC = "size"

    def __init__(self, attribute: Operand):
        self.attr = attribute
        super().__init__(attribute)

    def expr(self, item: Optional[Item]) -> int:  # type: ignore[override]
        if self.attr.get_type(item) is None:
            raise ValueError(f"Invalid attribute name {self.attr}")

        if self.attr.get_type(item) in ("S", "SS", "NS", "B", "BS", "L", "M"):
            return len(self.attr.expr(item))
        raise ValueError("Invalid filter expression")


class FuncBetween(Func):
    FUNC = "BETWEEN"

    def __init__(self, attribute: Operand, start: Operand, end: Operand):
        self.attr = attribute
        self.start = start
        self.end = end
        super().__init__(attribute, start, end)

    def expr(self, item: Optional[Item]) -> bool:
        # In python3 None is not a valid comparator when using < or > so must be handled specially
        start = self.start.expr(item)
        attr = self.attr.expr(item)
        end = self.end.expr(item)
        # Need to verify whether start has a valid value
        # Can't just check  'if start', because start could be 0, which is a valid number
        start_has_value = start is not None and (isinstance(start, Decimal) or start)
        end_has_value = end is not None and (isinstance(end, Decimal) or end)
        if start_has_value and attr and end_has_value:
            return start <= attr <= end
        elif start is None and attr is None:
            # None is between None and None as well as None is between None and any number
            return True
        elif start is None and attr and end:
            return attr <= end
        else:
            return False


class FuncIn(Func):
    FUNC = "IN"

    def __init__(self, attribute: Operand, *possible_values: Any):
        self.attr = attribute
        self.possible_values = possible_values
        super().__init__(attribute, *possible_values)

    def expr(self, item: Optional[Item]) -> bool:
        for possible_value in self.possible_values:
            if self.attr.expr(item) == possible_value.expr(item):
                return True

        return False


COMPARATOR_CLASS = {
    "<": OpLessThan,
    ">": OpGreaterThan,
    "<=": OpLessThanOrEqual,
    ">=": OpGreaterThanOrEqual,
    "=": OpEqual,
    "<>": OpNotEqual,
}

FUNC_CLASS: dict[str, Any] = {
    "attribute_exists": FuncAttrExists,
    "attribute_not_exists": FuncAttrNotExists,
    "attribute_type": FuncAttrType,
    "begins_with": FuncBeginsWith,
    "contains": FuncContains,
    "size": FuncSize,
    "between": FuncBetween,
}
TW_EOF
mkdir -p moto/dynamodb/models
cat > moto/dynamodb/models/dynamo_type.py <<'TW_EOF'
import base64
import copy
from decimal import Decimal
from typing import Any, Optional, Union, cast

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.utils import merge_dicts

from moto.core.common_models import BaseModel
from moto.dynamodb.exceptions import (
    EmptyKeyAttributeException,
    IncorrectDataType,
    ItemSizeTooLarge,
)
from moto.utilities.utils import md5_hash

from .utilities import bytesize, find_nested_key

deserializer = TypeDeserializer()
serializer = TypeSerializer()


class DDBType:
    """
    Official documentation at https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_AttributeValue.html
    """

    BINARY_SET = "BS"
    NUMBER_SET = "NS"
    STRING_SET = "SS"
    STRING = "S"
    NUMBER = "N"
    MAP = "M"
    LIST = "L"
    BOOLEAN = "BOOL"
    BINARY = "B"
    NULL = "NULL"


class DDBTypeConversion:
    _human_type_mapping = {
        val: key.replace("_", " ")
        for key, val in DDBType.__dict__.items()
        if key.upper() == key
    }

    @classmethod
    def get_human_type(cls, abbreviated_type: str) -> str:
        """
        Args:
            abbreviated_type(str): An attribute of DDBType

        Returns:
            str: The human-readable form of the DDBType.
        """
        return cls._human_type_mapping.get(abbreviated_type, abbreviated_type)


class DynamoType:
    """
    http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DataModel.html#DataModelDataTypes
    """

    def __init__(self, type_as_dict: Union["DynamoType", dict[str, Any]]):
        if type(type_as_dict) is DynamoType:
            self.type: str = type_as_dict.type
            self.value: Any = type_as_dict.value
        else:
            self.type = list(type_as_dict)[0]  # type: ignore[arg-type]
            self.value = list(type_as_dict.values())[0]  # type: ignore[union-attr]
        if self.is_list():
            self.value = [DynamoType(val) for val in self.value]
        elif self.is_map():
            self.value = {k: DynamoType(v) for k, v in self.value.items()}

    def __hash__(self) -> int:
        return hash((self.type, self.cast_value))

    def __eq__(self, other: "DynamoType") -> bool:  # type: ignore[override]
        return self.type == other.type and self.cast_value == other.cast_value

    def __ne__(self, other: "DynamoType") -> bool:  # type: ignore[override]
        return self.type != other.type or self.cast_value != other.cast_value

    def __lt__(self, other: "DynamoType") -> bool:
        return self.cast_value < other.cast_value

    def __le__(self, other: "DynamoType") -> bool:
        return self.cast_value <= other.cast_value

    def __gt__(self, other: "DynamoType") -> bool:
        return self.cast_value > other.cast_value

    def __ge__(self, other: "DynamoType") -> bool:
        return self.cast_value >= other.cast_value

    def __repr__(self) -> str:
        return f"DynamoType: {self.to_json()}"

    def __deepcopy__(self, memo: dict[int, Any]) -> "DynamoType":
        """Custom deepcopy that bypasses the expensive default pickle-based
        __reduce_ex__ protocol. Safe for DynamoDB AttributeValue trees,
        which are acyclic."""
        if id(self) in memo:  # pragma: no cover
            return memo[id(self)]  # Circular refs can't occur in DynamoDB data
        result = self.__class__.__new__(self.__class__)
        memo[id(self)] = result
        result.type = self.type
        if self.is_list():
            result.value = [copy.deepcopy(v, memo) for v in self.value]
        elif self.is_map():
            result.value = {k: copy.deepcopy(v, memo) for k, v in self.value.items()}
        elif self.is_set():
            result.value = list(self.value)
        else:
            result.value = self.value
        return result

    def __add__(self, other: "DynamoType") -> "DynamoType":
        if self.type != other.type:
            raise TypeError("Different types of operandi is not allowed.")
        if self.is_number():
            self_value: Union[Decimal, int] = (
                Decimal(self.value) if "." in self.value else int(self.value)
            )
            other_value: Union[Decimal, int] = (
                Decimal(other.value) if "." in other.value else int(other.value)
            )
            total = self_value + other_value
            return DynamoType({DDBType.NUMBER: f"{total}"})
        else:
            raise IncorrectDataType()

    def __sub__(self, other: "DynamoType") -> "DynamoType":
        if self.type != other.type:
            raise TypeError("Different types of operandi is not allowed.")
        if self.type == DDBType.NUMBER:
            self_value = float(self.value) if "." in self.value else int(self.value)
            other_value = float(other.value) if "." in other.value else int(other.value)
            return DynamoType({DDBType.NUMBER: f"{self_value - other_value}"})
        else:
            raise TypeError("Sum only supported for Numbers.")

    def __getitem__(self, item: "DynamoType") -> "DynamoType":
        if isinstance(item, str):
            # If our DynamoType is a map it should be subscriptable with a key
            if self.type == DDBType.MAP:
                return self.value[item]
        elif isinstance(item, int):
            # If our DynamoType is a list is should be subscriptable with an index
            if self.type == DDBType.LIST:
                return self.value[item]
        raise TypeError(
            f"This DynamoType {self.type} is not subscriptable by a {type(item)}"
        )

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(key, int):
            if self.is_list():
                if key >= len(self.value):
                    # DynamoDB doesn't care you are out of box just add it to the end.
                    self.value.append(value)
                else:
                    self.value[key] = value
        elif isinstance(key, str):
            if self.is_map():
                self.value[key] = value
        else:
            raise NotImplementedError(f"No set_item for {type(key)}")

    def __delitem__(self, item: str) -> "DynamoType":
        if isinstance(item, str) and self.type == DDBType.MAP:
            del self.value[item]
        return self

    @property
    def cast_value(self) -> Any:  # type: ignore[misc]
        if self.is_number():
            return Decimal(self.value)
        elif self.is_set():
            sub_type = self.type[0]
            return {DynamoType({sub_type: v}).cast_value for v in self.value}
        elif self.is_list():
            return [DynamoType(v).cast_value for v in self.value]
        elif self.is_map():
            return {k: DynamoType(v).cast_value for k, v in self.value.items()}
        elif self.is_null():
            return None
        else:
            return self.value

    def child_attr(self, key: Union[int, str, None]) -> Optional["DynamoType"]:
        """
        Get Map or List children by key. str for Map, int for List.

        Returns DynamoType or None.
        """
        if isinstance(key, str) and self.is_map():
            if key in self.value:
                return DynamoType(self.value[key])

        if isinstance(key, int) and self.is_list():
            idx = key
            if 0 <= idx < len(self.value):
                return DynamoType(self.value[idx])

        return None

    def size(self) -> int:
        if self.is_number():
            value_size = len(str(self.value))
        elif self.is_set():
            sub_type = self.type[0]
            value_size = sum([DynamoType({sub_type: v}).size() for v in self.value])
        elif self.is_list():
            value_size = sum([v.size() for v in self.value])
        elif self.is_map():
            value_size = sum(
                [bytesize(k) + DynamoType(v).size() for k, v in self.value.items()]
            )
        elif isinstance(self.value, bool):
            value_size = 1
        else:
            value_size = bytesize(self.value)
        return value_size

    def to_json(self) -> dict[str, Any]:
        # Returns a regular JSON object where the value can still be/contain a DynamoType
        if self.is_binary() and isinstance(self.value, bytes):
            # Binary data cannot be represented in JSON
            # AWS returns a base64-encoded value - the SDK's then convert that back
            return {self.type: base64.b64encode(self.value).decode("utf-8")}
        return {self.type: self.value}

    def to_regular_json(self) -> dict[str, Any]:
        # Returns a regular JSON object in full
        value = copy.deepcopy(self.value)
        if isinstance(value, dict):
            for key, nested_value in value.items():
                value[key] = (
                    nested_value.to_regular_json()
                    if isinstance(nested_value, DynamoType)
                    else nested_value
                )
        if isinstance(value, list):
            value = [
                val.to_regular_json() if isinstance(val, DynamoType) else val
                for val in value
            ]
        if self.is_binary():
            value = base64.b64decode(value)
        return {self.type: value}

    def compare(self, range_comparison: str, range_objs: list[Any]) -> bool:
        """
        Compares this type against comparison filters
        """
        from moto.dynamodb.comparisons import get_comparison_func

        range_values = [obj.cast_value for obj in range_objs]
        comparison_func = get_comparison_func(range_comparison)
        return comparison_func(self.cast_value, *range_values)

    def is_number(self) -> bool:
        return self.type == DDBType.NUMBER

    def is_set(self) -> bool:
        return self.type in (DDBType.STRING_SET, DDBType.NUMBER_SET, DDBType.BINARY_SET)

    def is_list(self) -> bool:
        return self.type == DDBType.LIST

    def is_map(self) -> bool:
        return self.type == DDBType.MAP

    def is_binary(self) -> bool:
        return self.type == DDBType.BINARY

    def is_null(self) -> bool:
        return self.type == DDBType.NULL

    def same_type(self, other: "DynamoType") -> bool:
        return self.type == other.type

    def pop(self, key: str, *args: Any, **kwargs: Any) -> None:
        if self.is_map() or self.is_list():
            self.value.pop(key, *args, **kwargs)
        else:
            raise TypeError(f"pop not supported for DynamoType {self.type}")


# https://github.com/getmoto/moto/issues/1874
# Ensure that the total size of an item does not exceed 400kb
class LimitedSizeDict(dict[str, Any]):
    def __init__(self, *args: Any, **kwargs: Any):
        self.update(*args, **kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        current_item_size = sum(
            [
                item.size() if type(item) is DynamoType else bytesize(str(item))
                for item in (list(self.keys()) + list(self.values()))
            ]
        )
        new_item_size = bytesize(key) + (
            value.size() if type(value) is DynamoType else bytesize(str(value))
        )
        # Official limit is set to 400000 (400KB)
        # Manual testing confirms that the actual limit is between 409 and 410KB
        # We'll set the limit to something in between to be safe
        if (current_item_size + new_item_size) > 405000:
            raise ItemSizeTooLarge
        super().__setitem__(key, value)


class Item(BaseModel):
    def __init__(
        self,
        hash_key: DynamoType,
        range_key: Optional[DynamoType],
        attrs: dict[str, Any],
    ):
        self.hash_key = hash_key
        self.range_key = range_key

        self.attrs = LimitedSizeDict()
        for key, value in attrs.items():
            self.attrs[key] = DynamoType(value)

    def __eq__(self, other: "Item") -> bool:  # type: ignore[override]
        return all(
            [
                self.hash_key == other.hash_key,
                self.range_key == other.range_key,  # type: ignore[operator]
                self.attrs == other.attrs,
            ]
        )

    def __repr__(self) -> str:
        return f"Item: {self.to_json()}"

    def __deepcopy__(self, memo: dict[int, Any]) -> "Item":
        """Custom deepcopy that bypasses the expensive default pickle-based
        __reduce_ex__ protocol, and skips LimitedSizeDict size validation
        during copy (the source item already passed validation on write)."""
        if id(self) in memo:  # pragma: no cover
            return memo[id(self)]  # Circular refs can't occur in DynamoDB data
        result = cast(Item, self.__class__.__new__(self.__class__))
        memo[id(self)] = result
        result.hash_key = copy.deepcopy(self.hash_key, memo)
        result.range_key = copy.deepcopy(self.range_key, memo)
        # Bypass LimitedSizeDict.__setitem__ which runs O(n) size validation on
        # every insert. The source item already passed validation, so re-checking
        # during copy is unnecessary and would make the overall copy O(n²).
        attrs_copy = LimitedSizeDict.__new__(LimitedSizeDict)
        dict.__init__(attrs_copy)
        for key, value in self.attrs.items():
            dict.__setitem__(attrs_copy, key, copy.deepcopy(value, memo))
        result.attrs = attrs_copy
        return result

    def size(self) -> int:
        return sum(bytesize(key) + value.size() for key, value in self.attrs.items())

    def to_json(self, root_attr_name: str = "Attributes") -> dict[str, Any]:
        attributes: dict[str, Any] = {}
        for attribute_key, attribute in self.attrs.items():
            if isinstance(attribute.value, dict):
                attr_dict_value = {
                    key: value.to_regular_json()
                    for key, value in attribute.value.items()
                }
                attributes[attribute_key] = {attribute.type: attr_dict_value}
            elif isinstance(attribute.value, list):
                attr_list_value = [
                    value.to_regular_json() if isinstance(value, DynamoType) else value
                    for value in attribute.value
                ]
                attributes[attribute_key] = {attribute.type: attr_list_value}
            else:
                attributes[attribute_key] = {attribute.type: attribute.value}

        return {root_attr_name: attributes}

    def to_regular_json(self) -> dict[str, Any]:
        attributes = {}
        for key, attribute in self.attrs.items():
            attributes[key] = deserializer.deserialize(attribute.to_regular_json())
        return attributes

    def describe_attrs(
        self, attributes: Optional[dict[str, Any]] = None
    ) -> dict[str, dict[str, Any]]:
        if attributes:
            included = {}
            for key, value in self.attrs.items():
                if key in attributes:
                    included[key] = value
        else:
            included = self.attrs
        return {"Item": included}

    def validate_no_empty_key_values(
        self, attribute_updates: dict[str, Any], key_attributes: list[str]
    ) -> None:
        for attribute_name, update_action in attribute_updates.items():
            action = update_action.get("Action") or "PUT"  # PUT is default
            if action == "DELETE":
                continue
            new_value = next(iter(update_action["Value"].values()))
            if action == "PUT" and new_value == "" and attribute_name in key_attributes:
                raise EmptyKeyAttributeException

    def update_with_attribute_updates(self, attribute_updates: dict[str, Any]) -> None:
        for attribute_name, update_action in attribute_updates.items():
            # Use default Action value, if no explicit Action is passed.
            # Default value is 'Put', according to
            # Boto3 DynamoDB.Client.update_item documentation.
            action = update_action.get("Action", "PUT")
            if action == "DELETE" and "Value" not in update_action:
                if attribute_name in self.attrs:
                    del self.attrs[attribute_name]
                continue
            new_value = list(update_action["Value"].values())[0]
            if action == "PUT":
                # TODO deal with other types
                if set(update_action["Value"].keys()) == {"SS"}:
                    self.attrs[attribute_name] = DynamoType({"SS": new_value})
                elif set(update_action["Value"].keys()) == {"NS"}:
                    self.attrs[attribute_name] = DynamoType({"NS": new_value})
                elif isinstance(new_value, list):
                    self.attrs[attribute_name] = DynamoType({"L": new_value})
                elif isinstance(new_value, dict):
                    self.attrs[attribute_name] = DynamoType({"M": new_value})
                elif set(update_action["Value"].keys()) == {"N"}:
                    self.attrs[attribute_name] = DynamoType({"N": new_value})
                elif set(update_action["Value"].keys()) == {"NULL"}:
                    if attribute_name in self.attrs:
                        del self.attrs[attribute_name]
                else:
                    self.attrs[attribute_name] = DynamoType({"S": new_value})
            elif action == "ADD":
                if set(update_action["Value"].keys()) == {"N"}:
                    existing = self.attrs.get(attribute_name, DynamoType({"N": "0"}))
                    self.attrs[attribute_name] = DynamoType(
                        {"N": str(Decimal(existing.value) + Decimal(new_value))}
                    )
                elif set(update_action["Value"].keys()) == {"SS"}:
                    existing = self.attrs.get(attribute_name, DynamoType({"SS": {}}))
                    new_set = set(existing.value).union(set(new_value))
                    self.attrs[attribute_name] = DynamoType({"SS": list(new_set)})
                elif set(update_action["Value"].keys()) == {"NS"}:
                    existing = self.attrs.get(attribute_name, DynamoType({"NS": {}}))
                    new_set = set(existing.value).union(set(new_value))
                    self.attrs[attribute_name] = DynamoType({"NS": list(new_set)})
                elif set(update_action["Value"].keys()) == {"L"}:
                    existing = self.attrs.get(attribute_name, DynamoType({"L": []}))
                    new_list = existing.value + new_value
                    self.attrs[attribute_name] = DynamoType({"L": new_list})
                else:
                    # TODO: implement other data types
                    raise NotImplementedError(
                        "ADD not supported for {}".format(
                            ", ".join(update_action["Value"].keys())
                        )
                    )
            elif action == "DELETE":
                if set(update_action["Value"].keys()) == {"SS"}:
                    existing = self.attrs.get(attribute_name, DynamoType({"SS": {}}))
                    new_set = set(existing.value).difference(set(new_value))
                    self.attrs[attribute_name] = DynamoType({"SS": list(new_set)})
                elif set(update_action["Value"].keys()) == {"NS"}:
                    existing = self.attrs.get(attribute_name, DynamoType({"NS": {}}))
                    new_set = set(existing.value).difference(set(new_value))
                    self.attrs[attribute_name] = DynamoType({"NS": list(new_set)})
                else:
                    raise NotImplementedError(
                        "ADD not supported for {}".format(
                            ", ".join(update_action["Value"].keys())
                        )
                    )
            else:
                raise NotImplementedError(
                    f"{action} action not support for update_with_attribute_updates"
                )

    def project(self, projection_expressions: list[list[str]]) -> "Item":
        # Returns a new Item with only the dictionary-keys that match the provided projection_expression
        # Will return an empty Item if the expression does not match anything
        result: dict[str, Any] = {}
        for expr in projection_expressions:
            x = find_nested_key(expr, self.to_regular_json())
            merge_dicts(result, x)

        return Item(
            hash_key=self.hash_key,
            range_key=self.range_key,
            # 'result' is a normal Python dictionary ({'key': 'value'}
            # We need to convert that into DynamoDB dictionary ({'M': {'key': {'S': 'value'}}})
            attrs=serializer.serialize(result)["M"],
        )

    def is_within_segment(
        self, segments: Union[tuple[None, None], tuple[int, int]]
    ) -> bool:
        """
        Segments can be either (x, y) or (None, None)
        None, None => the user requested the entire table, so the item always falls within that
        x, y       => the user requested segment x out of y

        Segment membership is computed based on the value of the hash key
        """
        if segments == (None, None):
            return True

        segment, total_segments = segments
        # Creates a reproducible hash number for this item (between 0 and 256)
        # Note that we can't use the builtin hash() method, as that is not deterministic between executions
        #
        # Using a hash based on the hash key ensures parity with how AWS seems to behave:
        #  - Items are not divided equally between segment
        #  - Items always fall in the same segment, regardless of how often you call `scan()`
        #  - Items with the same hash key but different range keys always fall in the same segment
        #  - Items with different hash keys may be part of different segments
        #
        item_hash = md5_hash(self.hash_key.value.encode("utf8")).digest()[0]
        # Modulo ensures that we always get a number between 0 and (total_segments)
        item_segment = item_hash % total_segments
        return segment == item_segment
TW_EOF
