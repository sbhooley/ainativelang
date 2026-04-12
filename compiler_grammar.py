"""
Compiler-owned formal prefix grammar/state machine for AINL decoding.

This module is the single source of truth for lexical + structural prefix
admissibility used by decoder constraints. Slot schemas for ops such as
``memory.merge`` / ``persona.update`` live in ``compiler_v2.OP_GRAMMAR`` and are
consumed via ``grammar_next_slot_classes`` / ``grammar_matches_token_class``.
It intentionally separates:
- structural plausibility (formal)
- semantic strict compilation (outside this module)
"""

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

from compiler_v2 import (
    AICodeCompiler,
    GRAMMAR_CLASS_ARROW_CONT,
    GRAMMAR_CLASS_GENERIC,
    GRAMMAR_CLASS_LABEL_ARROW_CONT,
    GRAMMAR_CLASS_LABEL_DECL,
    GRAMMAR_CLASS_LINE_STARTER,
    GRAMMAR_CLASS_MODULE_OP,
    GRAMMAR_CLASS_NEWLINE,
    GRAMMAR_CLASS_QUOTE_CLOSE,
    MODULE_ALIASES,
    OP_REGISTRY,
    grammar_active_label_scope,
    grammar_apply_candidate_to_prefix,
    grammar_next_slot_classes,
    grammar_prefix_completable,
    grammar_scan_lexical_prefix_state,
    grammar_is_label_decl,
    grammar_matches_token_class,
)

_COMPILER = AICodeCompiler()

TOP_LEVEL_OPS = {op for op, spec in OP_REGISTRY.items() if op != "L:" and spec.get("scope") in ("top", "any")}
ACTIVE_LABEL_LINE_STARTERS = {op for op, spec in OP_REGISTRY.items() if op != "L:" and spec.get("scope") in ("label", "any")}

_FORBIDDEN_SNIPPETS = ("```", "import ", "def ", "class ", "workflow:")

@dataclass(frozen=True)
class LexicalPrefixState:
    line: str
    in_quote: bool
    in_comment: bool
    ends_with_whitespace: bool
    token_in_progress: str
    tokens: List[str]

    @property
    def partial_arrow(self) -> bool:
        return self.token_in_progress in {"-", "->"}

    @property
    def partial_label_decl(self) -> bool:
        return bool(re.match(r"^L\d*$", self.token_in_progress or ""))

    @property
    def partial_module_prefix(self) -> bool:
        return self.token_in_progress.endswith(".")


@dataclass(frozen=True)
class PrefixParseState:
    prefix: str
    lex: LexicalPrefixState
    in_label_scope: bool
    current_op: Optional[str]
    slots: List[str]
    last_line_partial: bool


def _is_label_decl(tok: str) -> bool:
    return grammar_is_label_decl(tok)


def _canonical_op(first: str) -> str:
    if _is_label_decl(first):
        return "L:"
    return MODULE_ALIASES.get(first, first)


def is_prefix_anti_drift_clean(prefix: str) -> bool:
    low = (prefix or "").lower()
    return not any(s in low for s in _FORBIDDEN_SNIPPETS)


def scan_lexical_prefix_state(prefix: str) -> LexicalPrefixState:
    d = grammar_scan_lexical_prefix_state(prefix, tokenizer=_COMPILER)
    return LexicalPrefixState(
        line=str(d["line"]),
        in_quote=bool(d["in_quote"]),
        in_comment=bool(d["in_comment"]),
        ends_with_whitespace=bool(d["ends_with_whitespace"]),
        token_in_progress=str(d["token_in_progress"]),
        tokens=list(d["tokens"]),
    )


def compiler_prefix_completable(prefix: str) -> bool:
    return grammar_prefix_completable(prefix, tokenizer=_COMPILER)


def _compiler_active_label_scope(prefix: str) -> bool:
    return grammar_active_label_scope(prefix, tokenizer=_COMPILER)


def parse_prefix_state(prefix: str) -> PrefixParseState:
    lex = scan_lexical_prefix_state(prefix)
    current_op = _canonical_op(lex.tokens[0]) if lex.tokens else None
    slots = lex.tokens[1:] if lex.tokens else []
    return PrefixParseState(
        prefix=prefix,
        lex=lex,
        in_label_scope=_compiler_active_label_scope(prefix),
        current_op=current_op,
        slots=slots,
        last_line_partial=not (prefix or "").endswith("\n"),
    )


def _matches_token_class(token_class: str, tok: str) -> bool:
    return grammar_matches_token_class(token_class, tok)


def _expected_next_slot_classes(op: str, slots: List[str]) -> Set[str]:
    return set(grammar_next_slot_classes(op, slots))


def apply_candidate_to_prefix(prefix: str, cand: str) -> str:
    return grammar_apply_candidate_to_prefix(prefix, cand, tokenizer=_COMPILER)


def admissible_token_classes(state: PrefixParseState) -> Set[str]:
    lex = state.lex
    if lex.in_comment:
        return {GRAMMAR_CLASS_NEWLINE}
    if lex.in_quote:
        return {GRAMMAR_CLASS_QUOTE_CLOSE}
    if lex.partial_arrow:
        return {GRAMMAR_CLASS_ARROW_CONT} if lex.token_in_progress == "-" else {GRAMMAR_CLASS_LABEL_ARROW_CONT}
    if lex.token_in_progress == "->L":
        return {"LABEL_REF"}
    if lex.partial_label_decl:
        return {GRAMMAR_CLASS_LABEL_DECL}
    if lex.partial_module_prefix:
        return {GRAMMAR_CLASS_MODULE_OP}
    if not lex.tokens:
        return {GRAMMAR_CLASS_LINE_STARTER}
    classes = _expected_next_slot_classes(state.current_op or "", state.slots)
    return classes or {GRAMMAR_CLASS_GENERIC}


def formal_next_token_classes(prefix: str) -> Set[str]:
    """Authoritative formal next-token classes for a prefix."""
    return admissible_token_classes(parse_prefix_state(prefix))

def is_structurally_admissible_token(prefix: str, token: str) -> bool:
    state = parse_prefix_state(prefix)
    lex = state.lex
    if token == "\n":
        return True
    if lex.partial_arrow:
        if lex.token_in_progress == "-":
            return token == ">"
        if lex.token_in_progress == "->":
            return token == "L"
        return True
    if lex.token_in_progress == "->L":
        return bool(re.match(r"^->L\d+$", token or ""))
    if lex.in_quote:
        return token == '"'
    if lex.in_comment:
        return False
    if not lex.tokens:
        if _is_label_decl(token):
            return True
        starters = ACTIVE_LABEL_LINE_STARTERS if state.in_label_scope else TOP_LEVEL_OPS
        return _canonical_op(token) in starters or token == "L"
    slot_classes = _expected_next_slot_classes(state.current_op or "", state.slots)
    if slot_classes:
        return any(_matches_token_class(cls, token) for cls in slot_classes)
    return True


def filter_admissible_candidates(prefix: str, raw_candidates: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for cand in set(raw_candidates):
        if not is_structurally_admissible_token(prefix, cand):
            continue
        if compiler_prefix_completable(apply_candidate_to_prefix(prefix, cand)):
            out.add(cand)
    return out

def is_structurally_plausible_prefix(prefix: str) -> bool:
    if not is_prefix_anti_drift_clean(prefix):
        return False
    return compiler_prefix_completable(prefix)
