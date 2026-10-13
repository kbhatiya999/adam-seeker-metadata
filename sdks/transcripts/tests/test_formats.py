import os
import sys
import textwrap

from seeker_sdk_transcripts import parse_cues, pick_language, produce_finals, render  # noqa: E402


def test_prefers_manual_english_then_any_manual():
    assert pick_language({'subtitles': {'de': [], 'en': []}, 'automatic_captions': {'hi-orig': []}}) == ('en', False)
    assert pick_language({'subtitles': {'de': []}}) == ('de', False)


def test_automatic_prefers_original_language_over_translations():
    assert pick_language({'automatic_captions': {'en': [], 'ur': [], 'hi-orig': [], 'hi': []}}) == ('hi-orig', True)
    assert pick_language({'automatic_captions': {'ur': [], 'en': []}}) == ('en', True)


def test_live_chat_is_not_a_caption_track():
    assert pick_language({'subtitles': {'live_chat': []}, 'automatic_captions': {'hi-orig': []}}) == ('hi-orig', True)
    assert pick_language({'subtitles': {'live_chat': []}}) is None
    assert pick_language({}) is None


def write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body).lstrip(), encoding='utf-8')
    return str(p)


SRT = """
    1
    00:00:01,000 --> 00:00:02,000
    hello there

    2
    00:00:02,000 --> 00:00:03,500
    hello there

    3
    00:00:03,500 --> 00:00:04,000
    <i>general</i> kenobi
    """


def test_parse_srt_merges_repeats_and_strips_tags(tmp_path):
    cues = parse_cues(write(tmp_path, 'a.srt', SRT))
    assert cues == [(1.0, 3.5, 'hello there'), (3.5, 4.0, 'general kenobi')]


def test_parse_vtt_skips_header_and_settings(tmp_path):
    p = write(tmp_path, 'a.vtt', """
        WEBVTT
        Kind: captions
        Language: en

        00:00:01.000 --> 00:00:02.000 align:start position:0%
        one

        00:00:02.000 --> 00:00:03.000
        two
        """)
    assert parse_cues(p) == [(1.0, 2.0, 'one'), (2.0, 3.0, 'two')]


def test_parse_srv1_and_ttml(tmp_path):
    srv1 = write(tmp_path, 'a.srv1', '<?xml version="1.0"?><transcript><text start="1" dur="1.5">one &amp;amp; two</text></transcript>')
    ttml = write(tmp_path, 'a.ttml', '<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body><div><p begin="00:00:01.000" end="00:00:02.500">one</p></div></body></tt>')
    assert parse_cues(srv1) == [(1.0, 2.5, 'one & two')]
    assert parse_cues(ttml) == [(1.0, 2.5, 'one')]


def test_render_srt_vtt_txt():
    cues = [(1.0, 2.5, 'one'), (3661.25, 3662.0, 'two')]
    assert render(cues, 'txt') == 'one two\n'
    assert render(cues, 'srt') == '1\n00:00:01,000 --> 00:00:02,500\none\n\n2\n01:01:01,250 --> 01:01:02,000\ntwo\n'
    assert render(cues, 'vtt').startswith('WEBVTT\n\n00:00:01.000 --> 00:00:02.500\none\n')


def test_produce_finals_converts_and_removes_source(tmp_path):
    src = write(tmp_path, 'v.en.ttml', '<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body><div><p begin="00:00:01.000" end="00:00:02.000">one</p></div></body></tt>')
    out = produce_finals(src, str(tmp_path / 'v.en'), ('srt', 'txt'), keep_source=False)
    assert sorted(out) == ['srt', 'txt'] and not os.path.exists(src)
    assert (tmp_path / 'v.en.txt').read_text(encoding='utf-8') == 'one\n'
    src2 = write(tmp_path, 'w.ttml', '<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body><div><p begin="0" end="1s">x</p></div></body></tt>')
    produce_finals(src2, str(tmp_path / 'w'), ('vtt',), keep_source=True)
    assert os.path.exists(src2) and (tmp_path / 'w.vtt').exists()
