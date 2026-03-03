# Publisher

## Run a YouTube worker once

```powershell
cd C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire
python -m publisher.run --platform youtube

# restrict to a channel
python -m publisher.run --platform youtube --channel market_meltdowns
```

### Notes
- Uses Playwright persistent contexts bound to `profiles/<channel_name>/`.
- This worker currently performs a **stub publish**: it only opens YouTube Studio and verifies you're logged in.
- Next step: implement actual upload UI flow (file select, title/caption, publish/schedule, verify).
