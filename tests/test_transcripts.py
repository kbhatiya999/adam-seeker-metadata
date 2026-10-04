import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from transcripts import pick_language, to_plain_text  # noqa: E402


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


def test_plain_text_from_srt_drops_numbers_timestamps_and_repeats(tmp_path):
    p = write(tmp_path, 'a.srt', """
        1
        00:00:01,000 --> 00:00:02,000
        hello there

        2
        00:00:02,000 --> 00:00:03,000
        hello there

        3
        00:00:03,000 --> 00:00:04,000
        <i>general</i> kenobi
        """)
    assert to_plain_text(p) == 'hello there general kenobi'


def test_plain_text_from_vtt_skips_header(tmp_path):
    p = write(tmp_path, 'a.vtt', """
        WEBVTT
        Kind: captions
        Language: en

        00:00:01.000 --> 00:00:02.000 align:start position:0%
        one

        00:00:02.000 --> 00:00:03.000
        two
        """)
    assert to_plain_text(p) == 'one two'


def test_plain_text_from_srv1_and_ttml(tmp_path):
    srv1 = write(tmp_path, 'a.srv1', '<?xml version="1.0"?><transcript><text start="1" dur="1">one</text><text start="2" dur="1">two</text></transcript>')
    ttml = write(tmp_path, 'a.ttml', '<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body><div><p begin="0">one</p><p begin="1">two</p></div></body></tt>')
    assert to_plain_text(srv1) == 'one two'
    assert to_plain_text(ttml) == 'one two'
