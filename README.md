# cloro tool for Open WebUI

Give Open WebUI models five tools from [cloro](https://cloro.dev?utm_source=open-webui&utm_medium=byok):

| Tool | What it returns | cloro credits |
| --- | --- | --: |
| `google_search` | Google organic results, the AI Overview and the sources it cites, People also ask | 7 |
| `ask_chatgpt` | The answer that the ChatGPT web app shows, with its sources | 7 |
| `ask_google_ai_mode` | The answer that Google AI Mode shows, with its sources | 6 |
| `ask_gemini` | The answer that the Gemini web app shows, with its sources | 6 |
| `ask_bing_ai_mode` | The answer that Bing AI Mode shows, with its sources | 6 |

Each source is also sent to the chat as a citation. The free plan has 500 credits a month.

Use it to see what Google and the AI assistants tell users about a topic or a brand, and which pages they cite. For plain web search, a SERP-only provider costs less.

There are two ways to connect cloro to Open WebUI. Option 1 is this tool. Option 2 is cloro's hosted MCP server, which needs no code.

## Option 1: install the tool

1. Get an API key at [dashboard.cloro.dev/api-keys](https://dashboard.cloro.dev/api-keys?utm_source=open-webui&utm_medium=byok).
2. In Open WebUI, open **Workspace > Tools** and select **Create**. Paste the contents of [`cloro_tool.py`](cloro_tool.py) and save. You can also get it from the Open WebUI community site, or use **Import from URL** with the raw URL of `cloro_tool.py`.
3. Select **Valves** (the gear icon on the tool's row). Set:
   - `api_key`: your cloro API key.
   - `country`: the default country, as an ISO 3166-1 alpha-2 code (default `US`). The model can set a different country for each call.
4. Turn the tool on for a model (**Workspace > Models**, edit the model, **Tools**) or for one chat (the **Integrations** menu in the message input).

Example prompts:

- "What does ChatGPT recommend for best CRM for startups, and which sources does it cite?"
- "Does Google's AI Overview for 'ai visibility tracking' cite example.com? Check in the US and Germany."
- "Compare the Gemini and Google AI Mode answers for 'best running shoes for flat feet'."
- "What does Bing AI Mode say about example.com, and which pages does it cite?"

The tool needs `httpx` and `pydantic`, which Open WebUI already installs.

## Option 2: connect the hosted MCP server

Open WebUI supports MCP servers over Streamable HTTP from version 0.6.31. cloro's server is at `https://mcp.cloro.dev/mcp`.

1. As an admin, open **Admin Panel > Settings > Integrations**.
2. Under **Tools > External Tool Servers**, select **+** (Add Connection).
3. Select the **Type** value until it shows **MCP Streamable HTTP**.
4. Set **URL** to `https://mcp.cloro.dev/mcp`.
5. Set **Auth** to **Bearer** and paste your cloro API key in the key field.
6. Set **Connection ID** and **Name**, for example `cloro`.
7. Open **Advanced** and set **Function Name Filter List** to:

   ```
   scrape_google, scrape_chatgpt, scrape_google_ai_mode, scrape_bing_aimode, scrape_gemini, resolve_google_redirect, list_countries
   ```

   The server also lists tools for other engines. Use only the tools in this list. The filter hides the others from the model.
8. Set **Access Control** for the users who can use the server, then save.
9. Turn the server on for a model or a chat, as in step 4 of Option 1.

Each MCP tool call is a sync request. It costs the engine's credits plus a 2-credit sync surcharge (see [providers and pricing](https://cloro.dev/docs/guides/providers?utm_source=open-webui&utm_medium=byok)). `list_countries` is free and `resolve_google_redirect` costs 1 credit.

Open WebUI shows a warning that its MCP support is experimental. If the model does not call the tools, use a model with reliable native tool calling.

## Tests

The tests stub HTTP. They do not call the cloro API.

```bash
uv run --with pytest --with httpx --with pydantic pytest -q
```

Set `CLORO_CAPTURE_DIR` to a folder of saved cloro responses (`google.json`, `chatgpt.json`, `aimode.json`, `gemini.json`, `badkey.json`, ...) to also parse those files.

## License

MIT
