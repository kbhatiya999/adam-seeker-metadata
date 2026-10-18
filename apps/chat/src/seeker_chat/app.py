"""Chainlit app: `seeker-chat` (or `mise run local:chat:up`) starts it. The logic is in core.py."""

import chainlit as cl
from chainlit.input_widget import Select

from seeker_sdk_llm import Waiting

from seeker_chat import core


@cl.set_chat_profiles
async def chat_profiles(current_user=None, language=None):
    found = core.pairs(core.root())
    if not found:
        return [cl.ChatProfile(name="nothing-processed", display_name="Nothing processed yet",
                               markdown_description=core.NOTHING_PROCESSED)]
    return [cl.ChatProfile(name=p.name, display_name=p.label, markdown_description=p.description,
                           default=(i == 0),
                           starters=[cl.Starter(label=label, message=q) for label, q in core.starters(core.root(), p)])
            for i, p in enumerate(found)]


@cl.on_chat_start
async def start():
    await cl.ChatSettings([Select(id="model", label="Gemini model (each has its own free daily quota)",
                                  values=core.MODELS, initial_index=0)]).send()
    cl.user_session.set("model", core.MODELS[0])
    pair = core.find(core.root(), cl.user_session.get("chat_profile"))
    if pair is None:
        await cl.Message(content=core.NOTHING_PROCESSED).send()
    elif not (cl.user_session.get("env") or {}).get(core.KEY_ENV):
        await cl.Message(content=core.NO_KEY).send()


@cl.on_settings_update
async def settings(values):
    cl.user_session.set("model", values.get("model") or core.MODELS[0])


@cl.on_message
async def on_message(message: cl.Message):
    pair = core.find(core.root(), cl.user_session.get("chat_profile"))
    if pair is None:
        await cl.Message(content=core.NOTHING_PROCESSED).send()
        return
    key = ((cl.user_session.get("env") or {}).get(core.KEY_ENV) or "").strip()
    if not key:
        await cl.Message(content=core.NO_KEY).send()
        return
    try:
        result, runner = await cl.make_async(core.answer)(message.content, pair, key, core.root(),
                                                         cl.user_session.get("model"))
    except Exception as e:   # a refused key, a request Gemini rejects ...
        await cl.Message(content=f"Sorry, that did not work: {e}").send()
        return
    if isinstance(result, Waiting):
        await cl.Message(content=core.waiting_text(runner)).send()
        return
    async with cl.Step(name="Search", type="retrieval") as step:
        step.output = core.search_details(result)
    await cl.Message(content=core.format_answer(result)).send()
