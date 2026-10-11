#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p text_to_num/lang
cat > text_to_num/lang/german.py <<'TW_EOF'
# MIT License

# Copyright (c) 2018-2019 Groupe Allo-Media

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import Dict, Optional
import re

from .base import Language

#
# CONSTANTS
# Built once on import.
#

# Those words multiplies lesser numbers (see Rules)
# Special case: "hundred" is processed apart.
MULTIPLIERS = {
    "tausend": 1_000,
    "million": 1_000_000,
    "millionen": 1_000_000,
    "milliarde": 1_000_000_000,
    "milliarden": 1_000_000_000,
    "billion": 1_000_000_000_000,
    "billionen": 1_000_000_000_000,
    "billiarde": 1_000_000_000_000_000,
    "billiarden": 1_000_000_000_000_000,
    "trillion": 1_000_000_000_000_000_000,
    "trillionen": 1_000_000_000_000_000_000,
    "trilliarde": 1_000_000_000_000_000_000_000,
    "trilliarden": 1_000_000_000_000_000_000_000,
}

# Units are terminals (see Rules)
# Special case: "zero/O" is processed apart.
UNITS: Dict[str, int] = {
    word: value
    for value, word in enumerate(
        "eins zwei drei vier fünf sechs sieben acht neun".split(), 1
    )
}
# Unit variants
UNITS["ein"] = 1    # TODO: use that this can be followed only by "100", "1000", "und"
UNITS["eine"] = 1   # TODO: use that this can be followed only by multipliers > 1000

# Single tens are terminals (see Rules)
STENS: Dict[str, int] = {
    word: value
    for value, word in enumerate(
        "zehn elf zwölf dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn".split(),
        10,
    )
}

# Ten multiples
# Ten multiples may be followed by a unit only;
MTENS: Dict[str, int] = {
    word: value * 10
    for value, word in enumerate(
        "zwanzig dreißig vierzig fünfzig sechzig siebzig achtzig neunzig".split(), 2
    )
}

# Ten multiples that can be combined with STENS
# MTENS_WSTENS: Set[str] = set()

# "hundred" has a special status (see Rules)
HUNDRED = {"hundert": 100}  # einhundert?

# All number words

NUMBERS = MULTIPLIERS.copy()
NUMBERS.update(UNITS)
NUMBERS.update(STENS)
NUMBERS.update(MTENS)
NUMBERS.update(HUNDRED)
# NUMBERS.update(COMPOSITES) # COMPOSITES are already in STENS for the German language

AND = "und"
ZERO = {"null"}

# Sort all numbers by length and start with the longest (we keep dict structure)
ALL_WORDS_SORTED_REVERSE = dict(sorted(
    # add "und" and "null" to NUMBERS
    {"und": None, "null": 0, **NUMBERS}.items(),
    # take reverse length of keys to sort
    key=lambda kv: len(kv[0]),
    reverse=True
))


class German(Language):

    # TODO: can this be replaced entirely?
    # Currently it has to be imported into 'parsers' as well ...
    NUMBER_DICT_GER = {"null": 0, **NUMBERS}

    ORDINALS_FIXED_GER = {
        "erste": "eins",
        "dritte": "drei",
        "sechste": "sechs",     # we need this because it ends with "s" ^^
        "siebte": "sieben",
        "achte": "acht"
    }
    LARGE_ORDINAL_SUFFIXES_GER = r"^(ster|stes|sten|ste)(\s|$)"  # RegEx for ord. > 19

    MULTIPLIERS = MULTIPLIERS
    UNITS = UNITS
    STENS = STENS
    MTENS = MTENS
    # MTENS_WSTENS = MTENS_WSTENS
    HUNDRED = HUNDRED
    NUMBERS = NUMBERS

    SIGN = {"plus": "+", "minus": "-"}
    ZERO = ZERO
    DECIMAL_SEP = "komma"
    DECIMAL_SYM = ","

    # AND_NUMS = set(UNITS.keys()).union(set(STENS.keys()).union(set(MTENS.keys())))
    AND = AND

    NEVER_IF_ALONE = {"ein", "eine"}
    NEVER_CONNECTS_WITH_AND = {"eins", "eine"}

    # Relaxed composed numbers (two-words only)
    # start => (next, target)
    # RELAXED: Dict[str, Tuple[str, str]] = {}  # TODO: not supported yet

    def ord2card(self, word: str) -> Optional[str]:
        """Convert ordinal number to cardinal.
        Return None if word is not an ordinal or is better left in letters.
        """
        if len(word) > 4:
            word_base = None
            # example transf.: zwanzigster -> zwanzigste -> zwanzigs -> zwanzig
            if word.endswith("ter") or word.endswith("tes") or word.endswith("ten"):
                word_base = word[:-1].lower()       # e.g. erster -> erste
            elif word.endswith("te"):
                word_base = word.lower()
            if word_base:
                if word_base in self.ORDINALS_FIXED_GER:
                    return self.ORDINALS_FIXED_GER[word_base]
                else:
                    word_base = word_base[:-2]      # e.g. vierte -> vier
                    if word_base.endswith("s"):
                        word_base = word_base[:-1]  # e.g. zwanzigs -> zwanzig
                    if word_base in self.NUMBER_DICT_GER:
                        return word_base
                    # here we could still have e.g: "zweiundzwanzig"
                    if word_base.endswith(tuple(self.NUMBER_DICT_GER)):
                        # once again split - TODO: we should try to reduce split calls
                        word_base_split = self.split_number_word(word_base).split()
                        wbs_length = len(word_base_split)
                        if (
                            wbs_length > 0
                            and word_base_split[wbs_length - 1] in self.NUMBER_DICT_GER
                        ):
                            return "".join(word_base_split)
                    return None
            else:
                return None
        else:
            return None

    def num_ord(self, digits: str, original_word: str) -> str:
        """Add suffix to number in digits to make an ordinal"""
        return f"{digits}."

    def normalize(self, word: str) -> str:
        return word

    def split_number_word(self, word: str) -> str:
        """Splits number words into separate words, e.g.
        einhundertfünzig -> ein hundert fünfzig
        """
        text = word.lower()  # NOTE: if we want to use this outside it should keep case
        invalid_word = ""
        result = ""
        while len(text) > 0:
            # start with the longest
            found = False
            for sw, int_num in ALL_WORDS_SORTED_REVERSE.items():
                # Check at the beginning of the current sentence for the longest word in ALL_WORDS
                if text.startswith(sw):
                    if len(invalid_word) > 0:
                        result += invalid_word + " "
                        invalid_word = ""
                    result += sw + " "
                    text = text[len(sw):]
                    found = True
                    break
            # current beginning could not be assigned to a word:
            if not found:
                # is (large) ordinal ending?
                ord_match = None
                if len(result) > 3 and text.startswith("ste"):
                    ord_match = re.search(self.LARGE_ORDINAL_SUFFIXES_GER, text)

                if ord_match:
                    # add ordinal ending
                    end = ord_match.span()[1]
                    # result = result[:-1] + text[start:end]   # drop last space and add suffix
                    text = text[end:]
                    invalid_word = ""
                elif not text[0] == " ":
                    # move one index
                    invalid_word += text[0:1]
                    text = text[1:]
                else:
                    if len(invalid_word) > 0:
                        result += invalid_word + " "
                        invalid_word = ""
                    text = text[1:]
        if len(invalid_word) > 0:
            result += invalid_word + " "
        return result
TW_EOF
mkdir -p text_to_num
cat > text_to_num/parsers.py <<'TW_EOF'
# MIT License

# Copyright (c) 2018-2019 Groupe Allo-Media

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
Convert spelled numbers into numeric values or digit strings.
"""

from typing import List, Optional

from text_to_num.lang import Language
from text_to_num.lang.german import German  # TODO: optimize and remove


class WordStreamValueParserInterface:
    """Interface for language-dependent 'WordStreamValueParser'"""

    def __init__(self, lang: Language, relaxed: bool = False) -> None:
        """Initialize the parser."""
        self.lang = lang
        self.relaxed = relaxed

    def push(self, word: str, look_ahead: Optional[str] = None) -> bool:
        """Push next word from the stream."""
        return NotImplemented

    def parse(self, text: str) -> bool:
        """Parse whole text (or fail)."""
        return NotImplemented

    @property
    def value(self) -> int:
        """At any moment, get the value of the currently recognized number."""
        return NotImplemented


class WordStreamValueParser(WordStreamValueParserInterface):
    """The actual value builder engine.

    The engine incrementaly recognize a stream of words as a valid number and build the
    corresponding numeric (integer) value.

    The algorithm is based on the observation that humans gather the
    digits by group of three to more easily speak them out.
    And indeed, the language uses powers of 1000 to structure big numbers.

    Public API:

        - ``self.push(word)``
        - ``self.value: int``
    """

    def __init__(self, lang: Language, relaxed: bool = False) -> None:
        """Initialize the parser.

        If ``relaxed`` is True, we treat the sequences described in
        ``lang.RELAXED`` as single numbers.
        """
        super().__init__(lang, relaxed)
        self.skip: Optional[str] = None
        self.n000_val: int = 0  # the number value part > 1000
        self.grp_val: int = 0  # the current three digit group value
        self.last_word: Optional[
            str
        ] = None  # the last valid word for the current group

    @property
    def value(self) -> int:
        """At any moment, get the value of the currently recognized number."""
        return self.n000_val + self.grp_val

    def group_expects(self, word: str, update: bool = True) -> bool:
        """Does the current group expect ``word`` to complete it as a valid number?
        ``word`` should not be a multiplier; multiplier should be handled first.
        """
        expected = False
        if self.last_word is None:
            expected = True
        elif (
            self.last_word in self.lang.UNITS
            and self.grp_val < 10
            or self.last_word in self.lang.STENS
            and self.grp_val < 20
        ):
            expected = word in self.lang.HUNDRED
        elif self.last_word in self.lang.MHUNDREDS:
            expected = True
        elif self.last_word in self.lang.MTENS:
            expected = (
                word in self.lang.UNITS
                or word in self.lang.STENS
                and self.last_word in self.lang.MTENS_WSTENS
            )
        elif self.last_word in self.lang.HUNDRED:
            expected = word not in self.lang.HUNDRED

        if update:
            self.last_word = word
        return expected

    def is_coef_appliable(self, coef: int) -> bool:
        if self.lang.simplify_check_coef_appliable:
            return coef != self.value

        """Is this multiplier expected?"""
        if coef > self.value and (self.value > 0 or coef >= 1000):
            # a multiplier can be applied to anything lesser than itself,
            # as long as it not zero (special case for 1000 which then implies 1)
            return True
        if coef * 1000 <= self.n000_val:
            # a multiplier can not be applied to a value bigger than itself,
            # so it must be applied to the current group only.
            # ex. for "mille": "deux millions cent cinquante mille"
            # ex. for "millions": "trois milliard deux cent millions"
            # But not twice: "dix mille cinq mille" is invalid for example. Therefore,
            # we test the 1000 × ``coef`` (as the multipliers above 100,
            # are a geometric progression of ratio 1000)
            return (
                self.grp_val > 0 or coef == 1000
            )  # "mille" without unit      is additive
        # TODO: There is one exception to the above rule: "de milliard"
        # ex. : "mille milliards de milliards"
        return False

    def push(self, word: str, look_ahead: Optional[str] = None) -> bool:
        """Push next word from the stream.

        Don't push punctuation marks or symbols, only words. It is the responsability
        of the caller to handle punctuation or any marker of pause in the word stream.
        The best practice is to call ``self.close()`` on such markers and start again after.

        Return ``True`` if  ``word`` contributes to the current value else ``False``.

        The first time (after instanciating ``self``) this function returns True marks
        the beginning of a number.

        If this function returns False, and the last call returned True, that means you
        reached the end of a number. You can get its value from ``self.value``.

        Then, to parse a new number, you need to instanciate a new engine and start
        again from the last word you tried (the one that has just been rejected).
        """
        if not word:
            return False

        if word == self.lang.AND and look_ahead in self.lang.AND_NUMS:
            return True

        word = self.lang.normalize(word)
        if word not in self.lang.NUMBERS:
            return False

        RELAXED = self.lang.RELAXED

        if word in self.lang.MULTIPLIERS:
            coef = self.lang.MULTIPLIERS[word]
            if not self.is_coef_appliable(coef):
                return False
            # a multiplier can not be applied to a value bigger than itself,
            # so it must be applied to the current group
            if coef < self.n000_val:
                self.n000_val = self.n000_val + coef * (
                    self.grp_val or 1
                )  # or 1 for "mille"
            else:
                self.n000_val = (self.value or 1) * coef

            self.grp_val = 0
            self.last_word = None
        elif (
            self.relaxed
            and word in RELAXED
            and look_ahead
            and look_ahead.startswith(RELAXED[word][0])
            and self.group_expects(RELAXED[word][1], update=False)
        ):
            self.skip = RELAXED[word][0]
            self.grp_val += self.lang.NUMBERS[RELAXED[word][1]]
        elif self.skip and word.startswith(self.skip):
            self.skip = None
        elif self.group_expects(word):
            if word in self.lang.HUNDRED:
                self.grp_val = (
                    100 * self.grp_val if self.grp_val else self.lang.HUNDRED[word]
                )
            elif word in self.lang.MHUNDREDS:
                self.grp_val = self.lang.MHUNDREDS[word]
            else:
                self.grp_val += self.lang.NUMBERS[word]
        else:
            self.skip = None
            return False
        return True


class WordStreamValueParserGerman(WordStreamValueParserInterface):
    """The actual value builder engine for the German language.

    The engine processes numbers blockwise and sums them up at the end.

    The algorithm is based on the observation that humans gather the
    digits by group of three to more easily speak them out.
    And indeed, the language uses powers of 1000 to structure big numbers.

    Public API:

        - ``self.parse(word)``
        - ``self.value: int``
    """

    def __init__(self, lang: Language, relaxed: bool = False) -> None:
        """Initialize the parser.

        If ``relaxed`` is True, we treat "ein und zwanzig" the same way as
        "einundzwanzig".
        """
        super().__init__(lang, relaxed)
        self.val: int = 0

    @property
    def value(self) -> int:
        """At any moment, get the value of the currently recognized number."""
        return self.val

    def parse(self, text: str) -> bool:
        """Check text for number words, split complex number words (hundertfünfzig)
        if necessary and parse all at once.
        """
        # Correct way of writing German numbers is one single word only if < 1 Mio.
        # We need to split to be able to parse the text:
        text = self.lang.split_number_word(text)
        # print("split text:", text) # for debugging

        STATIC_HUNDRED = "hundert"

        # Split text at MULTIPLIERS into 'num_groups'
        # E.g.: 53.243.724 -> drei und fünfzig Millionen
        # | zwei hundert drei und vierzig tausend | sieben hundert vier und zwanzig

        num_groups = []
        num_block = []
        text = text.lower()
        words = text.split()
        last_multiplier = None
        equation_results = []

        for w in words:
            num_block.append(w)
            if w in self.lang.MULTIPLIERS:
                num_groups.append(num_block.copy())
                num_block.clear()

                # check for multiplier errors (avoid numbers like "tausend einhundert zwei tausend)
                if last_multiplier is None:
                    last_multiplier = German.NUMBER_DICT_GER[w]
                else:
                    current_multiplier = German.NUMBER_DICT_GER[w]
                    if (
                        current_multiplier == last_multiplier
                        or current_multiplier > last_multiplier
                    ):
                        raise ValueError(
                            "invalid literal for text2num: {}".format(repr(w))
                        )

            # Also interrupt if there is any other word (no number, no AND)
            if w not in German.NUMBER_DICT_GER and w != self.lang.AND:
                raise ValueError("invalid literal for text2num: {}".format(repr(w)))

        if len(num_block) > 0:
            num_groups.append(num_block.copy())
            num_block.clear()

        main_equation = "0"
        ng = None

        while len(num_groups) > 0:
            if ng is None:
                ng = num_groups[0].copy()
            equation = ""
            processed_a_part = False

            sign_at_beginning = False
            if (len(ng) > 0) and (ng[0] in self.lang.SIGN):
                equation += self.lang.SIGN[ng[0]]
                ng.pop(0)
                equation_results.append(0)
                sign_at_beginning = True

            if sign_at_beginning and (
                (len(ng) == 0)
                or ((len(ng) > 0) and not ng[0] in German.NUMBER_DICT_GER)
            ):
                raise ValueError(
                    "invalid literal for text2num: {}".format(repr(num_groups))
                )

            # prozess zero(s) at the beginning
            null_at_beginning = False
            while (len(ng) > 0) and (ng[0] in self.lang.ZERO):
                equation += "0"
                ng.pop(0)
                equation_results.append(0)
                processed_a_part = True
                null_at_beginning = True

            if (
                null_at_beginning
                and (len(ng) > 0)
                and (not ng[0] == self.lang.DECIMAL_SYM)
            ):
                raise ValueError(
                    "invalid literal for text2num: {}".format(repr(num_groups))
                )

            # Process "hundert" groups first
            if STATIC_HUNDRED in ng:

                hundred_index = ng.index(STATIC_HUNDRED)
                if hundred_index == 0:
                    if equation == "":
                        equation = "100 "
                    else:
                        equation += " + 100 "
                    equation_results.append(100)
                    ng.pop(hundred_index)
                    processed_a_part = True

                elif (ng[hundred_index - 1] in self.lang.UNITS) or (
                    ng[hundred_index - 1] in self.lang.STENS
                ):
                    multiplier = German.NUMBER_DICT_GER[ng[hundred_index - 1]]
                    equation += "(" + str(multiplier) + " * 100)"
                    equation_results.append(multiplier * 100)
                    ng.pop(hundred_index)
                    ng.pop(hundred_index - 1)
                    processed_a_part = True

            # Process "und" groups
            if self.lang.AND in ng and len(ng) >= 3:
                and_index = ng.index(self.lang.AND)

                # what if "und" comes at the end or beginnig?
                if and_index + 1 >= len(ng) or and_index == 0:
                    raise ValueError(
                        "invalid 'and' index for text2num: {}".format(repr(ng))
                    )

                # get the number before and after the "und"
                first_summand = ng[and_index - 1]
                second_summand = ng[and_index + 1]

                # string to num for atomic numbers
                first_summand_num = German.NUMBER_DICT_GER[first_summand]
                second_summand_num = German.NUMBER_DICT_GER[second_summand]

                # not all combinations are allowed
                if (
                    first_summand_num >= 10
                    or second_summand_num < 20
                    or first_summand in German.NEVER_CONNECTS_WITH_AND
                ):
                    raise ValueError(
                        "invalid 'and' group for text2num: {}".format(repr(ng))
                    )

                and_sum_eq = "(" + str(first_summand_num) + " + " + str(second_summand_num) + ")"
                # Is there already a hundreds value in the equation?
                if equation == "":
                    equation += and_sum_eq
                else:
                    equation = "(" + equation + " + " + and_sum_eq + ")"
                equation_results.append(first_summand_num + second_summand_num)
                ng.pop(and_index + 1)
                ng.pop(and_index)
                ng.pop(and_index - 1)
                processed_a_part = True

            # MTENS (20, 30, 40 .. 90)
            elif any(x in ng for x in self.lang.MTENS):

                # expect exactly one - TODO: ??! O_o who can read this?
                mtens_res = [x for x in ng if x in self.lang.MTENS]
                if not len(mtens_res) == 1:
                    raise ValueError(
                        "invalid literal for text2num: {}".format(repr(ng))
                    )

                mtens_num = German.NUMBER_DICT_GER[mtens_res[0]]
                if equation == "":
                    equation += "(" + str(mtens_num) + ")"
                else:
                    equation = "(" + equation + " + (" + str(mtens_num) + "))"
                mtens_index = ng.index(mtens_res[0])
                equation_results.append(mtens_num)
                ng.pop(mtens_index)
                processed_a_part = True

            # 11, 12, 13, ... 19
            elif any(x in ng for x in self.lang.STENS):

                # expect exactly one
                stens_res = [x for x in ng if x in self.lang.STENS]
                if not len(stens_res) == 1:
                    raise ValueError(
                        "invalid literal for text2num: {}".format(repr(ng))
                    )

                stens_num = German.NUMBER_DICT_GER[stens_res[0]]
                if equation == "":
                    equation += "(" + str(stens_num) + ")"
                else:
                    equation = "(" + equation + " + (" + str(stens_num) + "))"
                stens_index = ng.index(stens_res[0])
                equation_results.append(stens_num)
                ng.pop(stens_index)
                processed_a_part = True

            # 1, 2, ... 9
            elif any(x in ng for x in self.lang.UNITS):

                # expect exactly one
                units_res = [x for x in ng if x in self.lang.UNITS]
                if not len(units_res) == 1:
                    raise ValueError(
                        "invalid literal for text2num: {}".format(repr(ng))
                    )

                units_num = German.NUMBER_DICT_GER[units_res[0]]
                if equation == "":
                    equation += "(" + str(units_num) + ")"
                else:
                    equation = "(" + equation + " + (" + str(units_num) + "))"
                units_index = ng.index(units_res[0])
                equation_results.append(units_num)
                ng.pop(units_index)
                processed_a_part = True

            # Add multipliers
            if any(x in ng for x in self.lang.MULTIPLIERS):
                # Multiplier is always the last word
                if ng[len(ng) - 1] in self.lang.MULTIPLIERS:
                    multiplier = German.NUMBER_DICT_GER[ng[len(ng) - 1]]
                    if len(ng) > 1:
                        # before last has to be UNITS, STENS or MTENS and cannot follow prev. num.
                        factor = German.NUMBER_DICT_GER[ng[len(ng) - 2]]
                        if len(equation_results) > 0:
                            # This prevents things like "zwei zweitausend" (DE) to become 4000
                            raise ValueError("invalid literal for text2num: {}".format(repr(ng)))
                        if factor and factor >= 1 and factor <= 90:
                            multiply_eq = "(" + str(factor) + " * " + str(multiplier) + ")"
                            if equation == "":
                                equation += multiply_eq
                            else:
                                equation += (" * " + multiply_eq)
                            equation_results.append(factor * multiplier)
                            ng.pop(len(ng) - 1)
                            processed_a_part = True
                        else:
                            # I think we should fail here instead of ignore?
                            raise ValueError("invalid literal for text2num: {}".format(repr(ng)))
                    else:
                        multiply_eq = "(" + str(multiplier) + ")"
                        if equation == "":
                            equation += multiply_eq
                        else:
                            equation += " * " + multiply_eq
                        equation_results.append(multiplier)
                    ng.pop(len(ng) - 1)
                    processed_a_part = True

            if not processed_a_part:
                raise ValueError("invalid literal for text2num: {}".format(repr(ng)))

            # done, remove number group
            if len(ng) == 0:
                num_groups.pop(0)
                if len(num_groups) > 0:
                    ng = num_groups[0].copy()
            else:
                # at this point there should not be any more number parts
                raise ValueError(
                    "invalid literal for text2num - group {} in {}".format(repr(num_groups), text)
                )

            # Any sub-equation that results to 0 and is not the first sub-equation means an error
            if (
                len(equation_results) > 1
                and equation_results[len(equation_results) - 1] == 0
            ):
                raise ValueError("invalid literal for text2num: {}".format(repr(text)))

            main_equation = main_equation + " + (" + equation + ")"
            # print("equation:", main_equation)  # for debugging
            # print("equation_results", equation_results)  # for debugging

        self.val = eval(main_equation)  # TODO: use 'equation_results' instead
        return True


class WordToDigitParser:
    """Words to digit transcriber.

    The engine incrementaly recognize a stream of words as a valid cardinal, ordinal,
    decimal or formal number (including leading zeros) and build the corresponding digit
    string.

    The submitted stream must be logically bounded: it is a phrase, it has a beginning
    and an end and does not contain sub-phrases. Formally, it does not contain punctuation
    nor voice pauses.

    For example, this text:

        « You don't understand. I want two cups of coffee, three cups of tea and an apple pie. »

    contains three phrases:

        - « you don't understand »
        - « I want two cups of coffee »
        - « three cups of tea and an apple pie »

    In other words, a stream must not cross (nor include) punctuation marks or voice pauses.
    Otherwise you may get unexpected, illogical, results. If you need to parse complete texts
    with punctuation, consider using `alpha2digit` transformer.

    Zeros are not treated as isolates but are considered as starting a new formal number
    and are concatenated to the following digit.

    Public API:

     - ``self.push(word, look_ahead)``
     - ``self.close()``
     - ``self.value``: str
    """

    def __init__(
        self,
        lang: Language,
        relaxed: bool = False,
        signed: bool = True,
        ordinal_threshold: int = 3,
    ) -> None:
        """Initialize the parser.

        If ``relaxed`` is True, we treat the sequence "quatre vingt" as
        a single "quatre-vingt".

        If ``signed`` is True, we parse signed numbers like
        « plus deux » (+2), or « moins vingt » (-20).

        Ordinals up to `ordinal_threshold` are not converted.
        """
        self.lang = lang
        self._value: List[str] = []
        self.int_builder = WordStreamValueParser(lang, relaxed=relaxed)
        self.frac_builder = WordStreamValueParser(lang, relaxed=relaxed)
        self.signed = signed
        self.in_frac = False
        self.closed = False  # For deferred stop
        self.open = False  # For efficiency
        self.last_word: Optional[str] = None  # For context
        self.ordinal_threshold = ordinal_threshold

    @property
    def value(self) -> str:
        """Return the current value."""
        return "".join(self._value)

    def close(self) -> None:
        """Signal end of input if input stream ends while still in a number.

        It's safe to call it multiple times.
        """
        if not self.closed:
            if self.in_frac and self.frac_builder.value:
                self._value.append(str(self.frac_builder.value))
            elif not self.in_frac and self.int_builder.value:
                self._value.append(str(self.int_builder.value))
            self.closed = True

    def at_start_of_seq(self) -> bool:
        """Return true if we are waiting for the start of the integer
        part or the start of the fraction part."""
        return (
            self.in_frac
            and self.frac_builder.value == 0
            or not self.in_frac
            and self.int_builder.value == 0
        )

    def at_start(self) -> bool:
        """Return True if nothing valid parsed yet."""
        return not self.open

    def _push(self, word: str, look_ahead: Optional[str]) -> bool:
        builder = self.frac_builder if self.in_frac else self.int_builder
        return builder.push(word, look_ahead)

    def is_alone(self, word: str, next_word: Optional[str]) -> bool:
        """Check if the word is 'alone' meaning its part of 'Language.NEVER_IF_ALONE'
        exceptions and has no other numbers around itself."""
        return (
            not self.open
            and word in self.lang.NEVER_IF_ALONE
            and self.lang.not_numeric_word(next_word)
            and self.lang.not_numeric_word(self.last_word)
            and not (next_word is None and self.last_word is None)
        )

    def push(self, word: str, look_ahead: Optional[str] = None) -> bool:
        """Push next word from the stream.

        Return ``True`` if  ``word`` contributes to the current value else ``False``.

        The first time (after instanciating ``self``) this function returns True marks
        the beginning of a number.

        If this function returns False, and the last call returned True, that means you
        reached the end of a number. You can get its value from ``self.value``.

        Then, to parse a new number, you need to instanciate a new engine and start
        again from the last word you tried (the one that has just been rejected).
        """
        if self.closed or self.is_alone(word, look_ahead):
            self.last_word = word
            return False

        if (
            self.signed
            and word in self.lang.SIGN
            and look_ahead in self.lang.NUMBERS
            and self.at_start()
        ):
            self._value.append(self.lang.SIGN[word])
        elif (
            word in self.lang.ZERO
            and self.at_start_of_seq()
            and (
                look_ahead is None
                or look_ahead in self.lang.NUMBERS
                or look_ahead in self.lang.ZERO
                or look_ahead in self.lang.DECIMAL_SEP
            )
        ):
            self._value.append("0")
        elif (
            word in self.lang.ZERO
            and self.at_start_of_seq()
            and look_ahead is not None
            and look_ahead in self.lang.DECIMAL_SEP
        ):
            pass
        elif self._push(self.lang.ord2card(word) or "", look_ahead):
            self._value.append(
                self.lang.num_ord(
                    str(
                        self.frac_builder.value
                        if self.in_frac
                        else self.int_builder.value
                    ),
                    word,
                )
                if self.int_builder.value > self.ordinal_threshold
                else word
            )
            self.closed = True
        elif (
            (word == self.lang.DECIMAL_SEP or word in self.lang.DECIMAL_SEP.split(','))
            and (look_ahead in self.lang.NUMBERS or look_ahead in self.lang.ZERO)
            and not self.in_frac
        ):
            if not self.value:
                self._value.append(str(self.int_builder.value))
            self._value.append(self.lang.DECIMAL_SYM)
            self.in_frac = True
        elif not self._push(word, look_ahead):
            if self.open:
                self.close()
            self.last_word = word
            return False

        self.open = True
        self.last_word = word
        return True
TW_EOF
mkdir -p text_to_num
cat > text_to_num/transforms.py <<'TW_EOF'
# MIT License

# Copyright (c) 2018-2019 Groupe Allo-Media

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
from itertools import dropwhile
from typing import Any, Iterator, List, Sequence, Tuple, Union, Optional

from .lang import LANG, Language, German, Portuguese
from .parsers import (
    WordStreamValueParserInterface,
    WordStreamValueParser,  # we should rename this to 'WordStreamValueParserCommon'
    WordStreamValueParserGerman,
    WordToDigitParser,
)

from text_to_num.lang.portuguese import OrdinalsMerger

omg = OrdinalsMerger()
USE_PT_ORDINALS_MERGER = True


def look_ahead(sequence: Sequence[Any]) -> Iterator[Tuple[Any, Any]]:
    """Look-ahead iterator.

    Iterate over a sequence by returning couples (current element, next element).
    The last couple returned before StopIteration is raised, is (last element, None).

    Example:

    >>> for elt, nxt_elt in look_ahead(sequence):
    ... # do something

    """
    maxi = len(sequence) - 1
    for i, val in enumerate(sequence):
        ahead = sequence[i + 1] if i < maxi else None
        yield val, ahead


def text2num(text: str, lang: Union[str, Language], relaxed: bool = False) -> int:
    """Convert the ``text`` string containing an integer number written as letters
    into an integer value.

    Set ``relaxed`` to True if you want to accept "quatre vingt(s)" as "quatre-vingt"
    (fr) or "ein und zwanzig" as "einundzwanzig" (de) etc..

    Raises an ValueError if ``text`` does not describe a valid number.
    Return an int.
    """
    language: Language
    # mypy seems unable to understand this
    language = LANG[lang] if type(lang) is str else lang  # type: ignore
    num_parser: WordStreamValueParserInterface

    # German
    if type(language) is German:
        # The German number writing rules do not apply to the common order of number processing
        num_parser = WordStreamValueParserGerman(
            language, relaxed=relaxed
        )
        num_parser.parse(text)
        return num_parser.value
    # Default
    else:
        num_parser = WordStreamValueParser(language, relaxed=relaxed)
        tokens = list(dropwhile(lambda x: x in language.ZERO, text.split()))
        if not all(num_parser.push(word, ahead) for word, ahead in look_ahead(tokens)):
            raise ValueError("invalid literal for text2num: {}".format(repr(text)))

    return num_parser.value


def alpha2digit(
    text: str,
    lang: str,
    relaxed: bool = False,
    signed: bool = True,
    ordinal_threshold: int = 3,
) -> str:
    """Return the text of ``text`` with all the ``lang`` spelled numbers converted to digits.
    Takes care of punctuation.
    Set ``relaxed`` to True if you want to accept some disjoint numbers as compounds.
    Set ``signed`` to False if you don't want to produce signed numbers, that is, for example,
    if you prefer to get « minus 2 » instead of « -2 ».

    Ordinals up to `ordinal_threshold` are not converted.
    """
    if lang not in LANG:
        raise Exception("Language not supported")

    language = LANG[lang]
    segments = re.split(
        r"\s*[\.,;\(\)…\[\]:!\?]+\s*", text
    )
    punct = re.findall(r"\s*[\.,;\(\)…\[\]:!\?]+\s*", text)
    if len(punct) < len(segments):
        punct.append("")

    # Process segments
    if type(language) is German:
        # TODO: we should try to build a proper 'WordToDigitParser' for German
        # and refactor the code to be more similar to the default logic below
        text = _alpha2digit_agg(
            language,
            segments,
            punct,
            relaxed=relaxed,
            signed=signed,
            ordinal_threshold=ordinal_threshold
        )
    else:
        # Default
        out_segments: List[str] = []
        for segment, sep in zip(segments, punct):
            tokens = segment.split()
            num_builder = WordToDigitParser(
                language,
                relaxed=relaxed,
                signed=signed,
                ordinal_threshold=ordinal_threshold,
            )
            in_number = False
            out_tokens: List[str] = []
            for word, ahead in look_ahead(tokens):
                if num_builder.push(word.lower(), ahead and ahead.lower()):
                    in_number = True
                elif in_number:
                    out_tokens.append(num_builder.value)
                    num_builder = WordToDigitParser(
                        language,
                        relaxed=relaxed,
                        signed=signed,
                        ordinal_threshold=ordinal_threshold,
                    )
                    in_number = num_builder.push(word.lower(), ahead and ahead.lower())
                if not in_number:
                    out_tokens.append(word)
            # End of segment
            num_builder.close()
            if num_builder.value:
                out_tokens.append(num_builder.value)
            out_segments.append(" ".join(out_tokens))
            out_segments.append(sep)
        text = "".join(out_segments)

    # Post-processing
    if type(language) is Portuguese and USE_PT_ORDINALS_MERGER:
        text = omg.merge_compound_ordinals_pt(text)

    return text


def _alpha2digit_agg(
    language: Language,
    segments: List[str],
    punct: List[Any],
    relaxed: bool,
    signed: bool,
    ordinal_threshold: int = 3
) -> str:
    """Variant for "agglutinative" languages and languages with different style
    of processing numbers, for example:

    Default parser: "twenty one" (en) = 20, 1, "vingt et un" (fr) = 20, 1
    German parser: "einundzwanzig" or "ein und zwanzig" (de) = 1, 20

    Only German for now.
    """
    out_segments: List[str] = []

    def revert_if_alone(sentence_effective_len: int, current_sentence: List[str]) -> bool:
        """Test if word is 'alone' and should not be shown as number."""
        # TODO: move this to Language?
        if sentence_effective_len == 1 and current_sentence[0].lower() in language.NEVER_IF_ALONE:
            return True
        else:
            return False

    for segment, sep in zip(segments, punct):
        tokens = segment.split()
        # TODO: Should we use 'split_number_word' once on each token here if relaxed=True?
        sentence: List[str] = []
        out_tokens: List[str] = []
        out_tokens_is_num: List[bool] = []
        out_tokens_ordinal_org: List[Optional[str]] = []
        combined_num_result = None
        current_token_ordinal_org = None
        reset_to_last_if_failed = False
        token_index = 0

        while token_index < len(tokens):
            t = tokens[token_index]
            token_to_add = None
            token_to_add_is_num = False
            tmp_token_ordinal_org = None
            cardinal_for_ordinal = language.ord2card(t)
            if cardinal_for_ordinal:
                tmp_token_ordinal_org = t
                t = cardinal_for_ordinal
            sentence.append(t)
            try:
                # TODO: this is very inefficient because we analyze the same text
                # again and again until it fails including 'split_number_word' and all the
                # heavy lifting ... but it works and is hard to optimize ¯\_(ツ)_/¯
                num_result = text2num(" ".join(sentence), language, relaxed=relaxed)
                # TODO: here we need to use 'relaxed' to check how to continue
                combined_num_result = num_result
                current_token_ordinal_org = tmp_token_ordinal_org
                token_index += 1
                reset_to_last_if_failed = False
                # ordinals end groups
                if current_token_ordinal_org and num_result > ordinal_threshold:
                    token_to_add = str(combined_num_result)
                    token_to_add_is_num = True
                # ... but ordinals threshold reverts number back
                elif current_token_ordinal_org:
                    current_token_ordinal_org = None
                    sentence[len(sentence)-1] = str(tmp_token_ordinal_org)
                    token_to_add = " ".join(sentence)
                    token_to_add_is_num = False
            except ValueError:
                # This will happen if look-ahead was required (e.g. because of AND) but failed:
                if reset_to_last_if_failed:
                    reset_to_last_if_failed = False
                    # repeat last try but ...
                    token_index -= 1
                    # ... finish old group first and clean up
                    token_to_add = str(combined_num_result)
                    token_to_add_is_num = True
                # Happens if a) ends with no num b) ends with AND c) ends with invalid next num:
                elif combined_num_result is not None:
                    if t == language.AND and (token_index + 1) < len(tokens):
                        # number might continue after AND
                        # test the next and then decide to keep it or reset group
                        reset_to_last_if_failed = True
                        token_index += 1
                    else:
                        # last token has to be tested again in case there is sth like "eins eins"
                        # finish LAST group but keep token_index
                        token_to_add = str(combined_num_result)
                        token_to_add_is_num = True
                else:
                    # previous text was not a valid number
                    # prep. for next group
                    token_index += 1
                    token_to_add = t
                    token_to_add_is_num = False
            # new grouped tokens? then add and prep. next
            if token_to_add:
                if token_to_add_is_num and revert_if_alone(len(sentence)-1, sentence):
                    token_to_add = str(sentence[0])
                    token_to_add_is_num = False
                    current_token_ordinal_org = None
                out_tokens.append(token_to_add)
                out_tokens_is_num.append(token_to_add_is_num)
                out_tokens_ordinal_org.append(current_token_ordinal_org)
                sentence.clear()
                combined_num_result = None
                current_token_ordinal_org = None

        # any remaining tokens to add?
        if combined_num_result is not None:
            if revert_if_alone(len(sentence), sentence):
                out_tokens.append(str(sentence[0]))
                out_tokens_is_num.append(False)
            else:
                out_tokens.append(str(combined_num_result))
                out_tokens_is_num.append(True)
            out_tokens_ordinal_org.append(None)  # we can't reach this if it was ordinal

        # join all and keep track on signs
        out_segment = ""
        num_of_tokens = len(out_tokens)
        next_is_decimal_num = False
        for index, ot in enumerate(out_tokens):
            if next_is_decimal_num:
                # continue decimals?
                if (
                    index < num_of_tokens - 1
                    and out_tokens_is_num[index + 1]
                    and int(out_tokens[index + 1]) < 10
                ):
                    out_segment += ot
                else:
                    next_is_decimal_num = False
                    out_segment += ot + " "
            elif (ot in language.SIGN) and signed:
                # sign check
                if index < num_of_tokens - 1:
                    if out_tokens_is_num[index + 1] is True:
                        out_segment += language.SIGN[ot]
            elif out_tokens_ordinal_org[index] is not None:
                # cardinal transform
                out_segment += language.num_ord(ot, str(out_tokens_ordinal_org[index])) + " "
            elif (
                (ot.lower() in language.DECIMAL_SEP)
                and index > 0 and index < num_of_tokens - 1
                and out_tokens_is_num[index - 1] and out_tokens_is_num[index + 1]
                and int(out_tokens[index + 1]) < 10
            ):
                # decimal
                out_segment = out_segment.strip() + language.DECIMAL_SYM
                next_is_decimal_num = True
            else:
                out_segment += ot + " "

        # print("all:", out_tokens, out_tokens_is_num, out_tokens_ordinal_org) # DEBUG
        out_segments.append(out_segment.strip())
        out_segments.append(sep)
    return "".join(out_segments)
TW_EOF
