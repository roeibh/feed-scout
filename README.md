# feed-scout

feed-scout is a Claude Code plugin that helps you keep up with a busy group chat. It reads what people shared since you last looked, works out which of it matters to you, and gives you a short list with a suggested next step for each item. It only suggests. You decide what to do, and you do it yourself.

## Install

In Claude Code:

```
/plugin marketplace add roeibh/feed-scout
/plugin install feed-scout@feed-scout
```

## Requirements

- Claude Code
- [wacli](https://github.com/openclaw/wacli), which reads the chat. Install it with Homebrew: `brew install openclaw/tap/wacli`
- Optional: Claude in Chrome, for pages that only open when you are logged in

## First run

Say "set up feed-scout". It checks wacli, learns what you work on from your local Claude Code files and a few questions, and lets you pick the chats to follow. After that, ask "anything good in the group?"

## License

MIT. See [LICENSE](LICENSE).
