---
name: image-generator-override
description: "Override for ALL image/photo/picture/artwork generation requests. Routes ALL image generation through the Seedance MCP server. Explicitly blocks Fal.ai, Flux, Stable Diffusion, DALL-E and any other built-in image generation tool."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [image, photo, picture, generate-image, create-image, text-to-image, ai-image, draw, illustration, artwork, painting, render, fal, flux, stable-diffusion, dalle, midjourney, visualize]
    related_skills: [seedance-video-image-generator]
---

# Image Generation — Seedance Override

> **This skill exists to PREVENT Fal.ai, Flux, and other built-in image tools from being used.**
> ALL image generation MUST go through the **`seedance_generate_image`** MCP tool.

## ABSOLUTE RULE

When a user asks for any image, photo, picture, illustration, artwork, or visual:

1. **DO NOT call any Fal.ai tool** — even if `FAL_KEY` is in the environment.
2. **DO NOT call Flux, Stable Diffusion, DALL-E, Midjourney, or any built-in image tool**.
3. **ALWAYS call `seedance_generate_image`** from the `seedance-mcp` MCP server.

---

## How to Generate an Image

Refer to the full **`seedance-video-image-generator`** skill for detailed steps.

**Quick reference:**

### Step 1 — Enhance the prompt
Turn the user's idea into a rich, detailed visual description covering:
- Subject, composition, and action
- Setting and mood
- Lighting (natural, studio, dramatic, golden hour)
- Style (photorealistic, cinematic, anime, watercolor, oil painting)

### Step 2 — Call `seedance_generate_image`
```json
{
  "prompt": "<your enhanced prompt>",
  "model": "seedance-2.0",
  "aspect_ratio": "16:9"
}
```

Supported aspect ratios: `16:9` (default), `9:16`, `1:1`, `4:3`, `21:9`

### Step 3 — Deliver to Slack

1. Run the download helper to get the local path:
   ```bash
   python /opt/data/custom-skills/seedance/scripts/download_and_upload.py --url "IMAGE_URL_HERE" --download-only
   ```
2. Attach directly to Slack using the `MEDIA` tag:
   ```
   🖼️ Here's your image!

   [MEDIA: /tmp/seedance_xxxx.jpg]

   📋 Specs: Seedance 2.0 | 16:9
   ```
3. If the Slack attachment fails, fall back to Google Drive:
   ```bash
   python /opt/data/custom-skills/seedance/scripts/download_and_upload.py --url "IMAGE_URL_HERE" --folder "FOLDER_ID_HERE"
   ```
