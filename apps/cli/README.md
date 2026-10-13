# seeker-cli

Thin command line over the Seeker SDKs. All logic lives in the SDKs.

```
seeker videos update | rebuild | manage ...
seeker transcripts [--method M] [--format F] [--final A,B] <stats|list-missing|download-missing|download|check|compare>
seeker plugins
```

Normally run through the mise tasks (`mise run local:videos:update`, ...).
