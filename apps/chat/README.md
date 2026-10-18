# seeker-chat

A Chainlit chat over the processed videos. Pick a strategy pair (how the transcripts were processed, how answers are
found), ask a question, and get an answer that cites the video and the time it is said.

```bash
mise run local:chat:up        # http://localhost:8000
```

- **Bring your own key:** the app asks each user for a Gemini API key (create one at
  https://aistudio.google.com/apikey). The key stays in that browser (localStorage) and is sent to this server only
  for that session; it is never saved (`persist_user_env = false`) and the form masks it.
- Only processed videos can be asked about: process them first with `seeker knowledge process` (or the Tilt and
  menu buttons). Answers come from the same chat strategies `seeker ask` and `seeker eval` use.
