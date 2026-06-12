---
name: seedance-video-generator
description: "Generate AI videos using ByteDance Seedance via the BytePlus Ark MCP server. Native tools: seedance_generate_video, seedance_generate_video_from_image."
version: 3.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [video, seedance, bytedance, generate, animate, render, tiktok, reels, portrait, landscape, cinematic, movie, film, text-to-video, image-to-video]
    related_skills: []
---

# Seedance Video Generator

Generate AI videos using ByteDance Seedance via the **`seedance_generate_video`** MCP tool.

## CRITICAL RULES

1. **Use the `seedance_generate_video` MCP tool** — do NOT use Luma AI, Kling, Runway, or any built-in video tool.
2. **Do NOT delegate to a subagent** — call the tool directly yourself.
3. **Always upload the generated video to Google Drive and return the shareable link** — direct Slack file uploads are disabled due to missing files:write scopes.
4. **Never output local paths or use local MEDIA tags** — if Google Drive upload fails, return a clear error message directly to the user. Do NOT mention local folders or paths.

---

## Step 1 — Enhance the prompt

Expand the user's idea into a rich cinematic description before calling the tool:
- Subject + Action
- Setting (location, time of day, weather)
- Camera (wide shot / tracking / drone / close-up)
- Lighting (golden hour / neon / dramatic / studio)
- Style (cinematic, hyperrealistic, dreamlike, anime)

**Example**: "Iron Man landing" →
> *"Iron Man in red and gold armor descending from the sky in a powerful superhero landing on a city street, one knee and fist hitting the ground creating a shockwave of dust and debris, dramatic slow-motion, cinematic lighting with smoke effects, photorealistic action movie style"*

---

## Step 2 — Choose parameters from the user's request

### Model
| User says | model value |
|---|---|
| "Seedance 2.0", "latest", "best quality", default | `seedance-2.0` |
| "Seedance 2.0 fast", "fast", "quick" | `seedance-2.0-fast` |
| "Seedance 1.5" | `seedance-1.5-pro` |
| "Seedance 1.0" | `seedance-1.0-pro` |
| "lite" | `seedance-1.0-lite` |

### Resolution
| User says | value |
|---|---|
| "480p", "low", "draft" | `480p` |
| default / "HD" | `720p` |
| "1080p", "high", "best" | `1080p` |

### Duration
| User says | value |
|---|---|
| default / "short" / "5 seconds" | `5` |
| "long" / "10 seconds" | `10` |

### Aspect Ratio
| User says | value |
|---|---|
| "landscape", "widescreen", default | `16:9` |
| "vertical", "portrait", "mobile", "TikTok", "Reels" | `9:16` |
| "square" | `1:1` |
| "ultrawide", "cinematic" | `21:9` |
| "standard" | `4:3` |

---

## Step 3 — Call `seedance_generate_video`

```json
{
  "prompt": "<your enhanced prompt>",
  "model": "seedance-2.0",
  "resolution": "720p",
  "duration": 5,
  "aspect_ratio": "16:9",
  "generate_audio": true
}
```

For image-to-video, use `seedance_generate_video_from_image` with an additional `image_url` parameter.

---

## Step 4 — Download, Upload to Google Drive, and Clean Up (MANDATORY)

Because direct Slack file uploads are disabled (due to missing files:write scopes in the Slack App token), you MUST use our robust helper script to download the video, upload it to Google Drive, share it publicly, and clean up the container's temporary files in a single step.

1. Find the `google_drive.folder_id` in `config.yaml` if it exists.
2. Call the helper script using the `terminal` tool:
   - If a folder ID is specified in `config.yaml` (e.g. `1-2hES89_Md5Mkhqo_a5EHRk-eJuNxlCT`):
     ```bash
     python /opt/data/custom-skills/seedance/scripts/download_and_upload.py --url "VIDEO_URL_HERE" --folder "FOLDER_ID_HERE"
     ```
   - If no folder ID is specified:
     ```bash
     python /opt/data/custom-skills/seedance/scripts/download_and_upload.py --url "VIDEO_URL_HERE"
     ```
3. The script will print the public Google Drive `webViewLink` on success.
4. Return this link to the user in Slack with a message like:
   ```
   🎬 Your superhero golden retriever video is ready!

   📋 Specs:
   • Model: Seedance 2.0 Fast
   • Duration: 5 seconds
   • Aspect ratio: 9:16 (portrait)
   • Resolution: 480p

   🔗 View/Download: <Google Drive Link>
   ```
5. **CRITICAL - Return Error on Failure**: If the script fails (non-zero exit code) or does not output a valid Google Drive Link, you MUST return a clean error message to the user (e.g., "Error: Failed to upload the generated video to Google Drive. Please try again."). Do NOT output local paths (such as `/opt/data/...` or `/documents/...`), do NOT suggest grabbing the file locally, and do NOT use any `MEDIA:` tag referencing a local file.
6. Do NOT leave any temporary files inside the container. The script automatically handles deleting the temporary file after upload.

## Other Available Seedance Tools

| Tool | Use when |
|---|---|
| `seedance_list_models` | User asks "what Seedance models are available?" |
| `seedance_list_resolutions` | User asks about supported resolutions/ratios |
| `seedance_get_task` | User asks to check on a previous generation |
