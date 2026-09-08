# Local source checkpoint

This is a selected source checkpoint, not a self-contained release or full disk backup.

Included: app source except app/config.py, tests except tests/unit/test_runtime_settings.py, presets, prompts, workers, pyproject.toml, uv.lock, README and ignore rules.

app/config.py and tests/unit/test_runtime_settings.py are intentionally held out because a conservative secret scan flagged credential-like literals. Their contents remain unchanged on disk. They require separate secret-safe review before inclusion. A fresh checkout alone is NOT runnable until local configuration is restored safely.

Excluded: models, private/runtime configuration, generated media, cache, databases, user projects, root experiment scripts, packaging scripts and miscellaneous local files. No data was deleted.

Acceptance for the quiz changes: latest targeted suite 15 passed; new-frame inspection shows series, explicit EXPERT label and answer fit. Fixtures test layout, not editorial difficulty or native fluency. Earlier 148-test quiz/Qt run passed. No new MP4/TTS/provider calls for this checkpoint.

Known limits: native-language and voice acceptance pending; persona output quality not established by tests; local media/model dependencies remain outside Git. No publish/push authorized.
