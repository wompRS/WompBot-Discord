"""Golden routing eval for LLMClient.should_search — the web-search gate.

These cases encode the *desired* routing decision for representative messages and
guard against the over/under-filtering regressions this gate has had before (e.g. a
polite "can you look up ..." must still search; "can you explain ..." must not).

should_search uses no instance state for an empty conversation context, so a bare
(un-__init__'d) instance is sufficient — and llm.py imports only `requests` + stdlib
at module load (the llmlingua/torch import is lazy), so this runs in the fast CI job.
"""
import pytest

from llm import LLMClient

_llm = LLMClient.__new__(LLMClient)


def _search(message: str) -> bool:
    return _llm.should_search(message, [])


SHOULD_SEARCH = [
    "what is the current price of bitcoin",
    "who won the f1 race today",
    "look up the latest news on tesla",
    "can you look up the current price of gold",   # polite wrapper — must still search
    "search for the best restaurants in tokyo",
    "what are the current nba standings",
    "whats the score of the lakers game",
    "is it true that the earth is flat",
    "what happened to twitter",
    "who is the ceo of openai",
]

SHOULD_NOT_SEARCH = [
    "what do you think about pineapple pizza",
    "how are you doing today",
    "explain how photosynthesis works",
    "can you explain recursion to me",             # polite wrapper, no factual trigger
    "tell me about yourself",
    "what did i say earlier",
    "how do i center a div",
    "what is a monad",
    "thanks that was helpful",
    "lol nice one",
]


@pytest.mark.parametrize("message", SHOULD_SEARCH)
def test_should_search_true(message):
    assert _search(message) is True, f"expected a web search for: {message!r}"


@pytest.mark.parametrize("message", SHOULD_NOT_SEARCH)
def test_should_search_false(message):
    assert _search(message) is False, f"did NOT expect a web search for: {message!r}"
