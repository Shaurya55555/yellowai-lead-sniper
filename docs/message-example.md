# Sample Slack output

This is the card **Post to Slack** produces (Block Kit). Replace with a real
screenshot once you run it.

---

**:dart: New high-value lead starred Shaurya55555/yellowai-lead-sniper-demo**

| | |
|---|---|
| **Name:** | Monalisa Octocat |
| **Company:** | GitHub |
| **Followers:** | 3421 |
| **Public repos:** | 88 |

**Bio:**
Design and build all the things. Interested in Open Source and AI.

**AI sales pitch:**
An OSS-focused engineer at GitHub with a large following and 88 public repos, this person shapes developer tooling decisions and could champion n8n internally and to their audience.

`github.com/octocat`

---

## Raw payload shape

```json
{
  "text": ":dart: New high-value lead starred Shaurya55555/yellowai-lead-sniper-demo",
  "blocks": [
    { "type": "section", "text": { "type": "mrkdwn", "text": "*:dart: New high-value lead starred Shaurya55555/yellowai-lead-sniper-demo*" } },
    { "type": "section", "fields": [
      { "type": "mrkdwn", "text": "*Name:*\nMonalisa Octocat" },
      { "type": "mrkdwn", "text": "*Company:*\nGitHub" },
      { "type": "mrkdwn", "text": "*Followers:*\n3421" },
      { "type": "mrkdwn", "text": "*Public repos:*\n88" }
    ] },
    { "type": "section", "text": { "type": "mrkdwn", "text": "*Bio:*\nDesign and build all the things. Interested in Open Source and AI." } },
    { "type": "section", "text": { "type": "mrkdwn", "text": "*AI sales pitch:*\n..." } },
    { "type": "context", "elements": [ { "type": "mrkdwn", "text": "<https://github.com/octocat|github.com/octocat>" } ] }
  ]
}
```
