---
name: seedance-video-image-generator
description: "Generate AI videos AND images using ByteDance Seedance via the BytePlus Ark MCP server. This skill MUST be used for all image and video generation requests. Do NOT use Fal.ai, Flux, or any built-in image tool. Native tools: seedance_generate_video, seedance_generate_video_from_image, seedance_generate_image."
version: 3.2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [video, image, photo, picture, generate, seedance, bytedance, animate, render, tiktok, reels, portrait, landscape, cinematic, movie, film, text-to-video, image-to-video, text-to-image, generate-image, generate-video, create-image, create-video, illustration, artwork, ai-image, ai-video, draw, painting]
    related_skills: []
---

# Seedance Video & Image Generator

Generate AI videos or images using ByteDance Seedance via the **`seedance_generate_video`** or **`seedance_generate_image`** MCP tools.

## CRITICAL RULES — READ FIRST, NEVER VIOLATE

1. **ALWAYS use `seedance_generate_image` for image/photo/picture requests** — do NOT use Fal.ai, Flux, Stable Diffusion, DALL-E, or ANY built-in image tool. If a `FAL_KEY` is present in the environment, IGNORE IT entirely.
2. **ALWAYS use `seedance_generate_video` for video/animation requests** — do NOT use Luma AI, Kling, Runway, or any built-in video tool.
3. **Do NOT delegate to a subagent** — call the tool directly yourself.
4. **Always prioritize direct Slack file attachments** using the `[MEDIA: /path/to/file]` syntax by downloading the file first. Only upload to Google Drive as a fallback if the Slack attachment fails.
5. **Never guess local paths** — always use the helper script to download the media locally before using the `MEDIA:` tag.
6. **Always use the high-detail `seedance-2.0` model** as the default. Do NOT automatically fall back to `seedance-2.0-fast` or any other model on timeout or delay. Only use the fast model if the user explicitly requests "fast" or "quick".

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

## Step 3 — Call `seedance_generate_video` or `seedance_generate_image`

**For Video:**
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

**For Image:**
```json
{
  "prompt": "<your enhanced prompt>",
  "model": "seedance-2.0",
  "aspect_ratio": "16:9"
}
```

For image-to-video, use `seedance_generate_video_from_image` with an additional `image_url` parameter.

---

## Step 4 — Download, Attach to Slack, and Google Drive Fallback

We prioritize native Slack attachments using the `[MEDIA: /path/to/file]` tag. Because the API returns a CDN URL, you must first download the file locally using the helper script.

**Phase 1: Direct Slack Attachment (Priority)**
1. Call the helper script with the `--download-only` flag to get a local path:
   ```bash
   python /opt/data/custom-skills/seedance/scripts/download_and_upload.py --url "VIDEO_OR_IMAGE_URL_HERE" --download-only
   ```
2. The script will output `Local Path: /tmp/seedance_xxxx.mp4`.
3. Reply to the user directly, embedding the path inside a `MEDIA` tag:
   ```
   🎬 Your superhero golden retriever is ready!

   [MEDIA: /tmp/seedance_xxxx.mp4]

   📋 Specs: Seedance 2.0 Fast, 5s, 9:16 (portrait)
   ```
   *Note: If the Slack workspace has issues with large files, the MEDIA tag might silently fail to appear in Slack. Wait for the user's feedback.*

**Phase 2: Google Drive Fallback**
1. **If the user explicitly tells you that the attachment failed or the video is missing**, fallback to Google Drive.
2. Find the `google_drive.folder_id` in `config.yaml` if it exists.
3. Call the helper script **without** `--download-only`:
   ```bash
   python /opt/data/custom-skills/seedance/scripts/download_and_upload.py --url "VIDEO_OR_IMAGE_URL_HERE" --folder "FOLDER_ID_HERE"
   ```
4. Return the generated Google Drive link to the user.

**Optional cleanup override flags (for the helper script):**
| Flag | Effect |
|---|---|
| *(none)* | Uses `cleanup.on_success` and `cleanup.on_failure` from `config.yaml` |
| `--no-cleanup` | Never delete the temp file, regardless of config |
| `--cleanup-on-failure` | Delete the temp file even if the upload fails |

## Other Available Seedance Tools

| Tool | Use when |
|---|---|
| `seedance_list_models` | User asks "what Seedance models are available?" |
| `seedance_list_resolutions` | User asks about supported resolutions/ratios |
| `seedance_get_task` | User asks to check on a previous generation |
