# Verified benchmark evidence explorer

Open index.html in a browser. Keep this folder with the report and runs when
sharing; the explorer itself works offline, while raw-evidence links require
the surrounding release folders. Controls read saved results and never start
an experiment. Start with Structured data / mgcrea typed to inspect the loss
and same-task raw recovery. The other tabs show real protocol task outcomes
and exhaustive finite repair diagnostics.

For a local preview from the repository root:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Open http://127.0.0.1:8765/demo/benchmark-v2/ . Raw result dictionaries and
source paths are available in data.json. The report states evidence scopes,
reproducible commands, failures and research work still outstanding.
