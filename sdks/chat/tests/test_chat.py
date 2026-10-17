from seeker_sdk_chat import (ANSWER_TOOL, EXPAND_TOOL, KeywordStrategy, MultilingualStrategy, Retriever, ask,
                             chat_strategy_names, get_chat_strategy, tokens)
from seeker_sdk_knowledge import KnowledgeStore, Passage
from seeker_sdk_llm import FakeProvider, Pending, ToolRunner, Waiting

PASSAGES = [
    Passage("v#c0", "v", 0, 180, "सूरह रात की आयत नंबर दो है अल्लाह ने पिलर्स के बिना", "Earth", "chunk"),
    Passage("v#c1", "v", 180, 360, "सही बुखारी की हदीस है 5686 मूत्र पियो", "Earth", "chunk"),
    Passage("v#n0", "v", 400, 460, "The host reads Quran 88:20: the earth is spread out like a bed.", "Earth", "argument"),
]


def test_tokens_keep_devanagari_words_whole_and_drop_stopwords():
    assert tokens("सही बुखारी की हदीस है 5686") == ["सही", "बुखारी", "हदीस", "5686"]
    assert tokens("What is Quran 13:2 about?") == ["quran", "13", "2"]
    assert tokens("সূরা আয়াত") == ["সূরা", "আয়াত"]


def test_bm25_finds_the_matching_script_only():
    index = Retriever(PASSAGES)
    assert [p.id for p in index.search("बुखारी 5686", 2)] == ["v#c1"]
    assert [p.id for p in index.search("Which verse says the earth is spread out?", 2)] == ["v#n0"]
    assert index.search("Bukhari urine", 3) == []   # English words do not match Devanagari captions
    fused = index.search_many(["Bukhari urine", "बुखारी मूत्र", "earth spread"], 3)
    assert [p.id for p in fused] == ["v#c1", "v#n0"]


def answers(request):
    if request.tool.name == "expand_query":
        return {"queries": ["बुखारी मूत्र", "bukhari peshab"]}
    ids = [p["id"] for p in request.input["passages"]]
    return {"answer": "In Earth the stream cites Sahih Bukhari 5686.", "citations": ids[:1] + ["invented#1"],
            "not_found": not ids}


def test_keyword_strategy_answers_from_retrieved_passages(tmp_path):
    runner = ToolRunner(FakeProvider(answers), str(tmp_path))
    result = KeywordStrategy(k=2).answer("बुखारी 5686 hadith", Retriever(PASSAGES), runner)
    assert result.citations == ["v#c1"] and not result.not_found  # the invented citation is dropped
    assert result.queries == ["बुखारी 5686 hadith"] and [p.id for p in result.retrieved] == ["v#c1"]
    nothing = KeywordStrategy().answer("Bukhari urine", Retriever(PASSAGES), runner)
    assert nothing.not_found and nothing.retrieved == []


def test_multilingual_strategy_expands_the_question_first(tmp_path):
    provider = FakeProvider(answers)
    result = MultilingualStrategy(k=2).answer("Which Bukhari number is about urine?", Retriever(PASSAGES),
                                              ToolRunner(provider, str(tmp_path)))
    assert [r.tool.name for r in provider.calls] == ["expand_query", "answer"]
    assert result.citations == ["v#c1"] and "बुखारी मूत्र" in result.queries


def test_waiting_when_the_model_has_not_answered(tmp_path):
    runner = ToolRunner(FakeProvider(lambda r: Pending(r.id)), str(tmp_path))
    assert MultilingualStrategy().answer("q", Retriever(PASSAGES), runner) == Waiting(1)
    assert KeywordStrategy().answer("earth spread", Retriever(PASSAGES), runner) == Waiting(1)


def test_ask_over_a_store_and_plugins(tmp_path):
    store = KnowledgeStore(str(tmp_path / "k"), "chunks", "v1")
    store.write("v", PASSAGES)
    result = ask("earth spread out", store, get_chat_strategy("keyword", k=1), ToolRunner(FakeProvider(answers), str(tmp_path)))
    assert result.citations == ["v#n0"]
    assert {"keyword", "multilingual"} <= set(chat_strategy_names())
    assert ANSWER_TOOL.key == "answer@v1" and EXPAND_TOOL.key == "expand_query@v1"
