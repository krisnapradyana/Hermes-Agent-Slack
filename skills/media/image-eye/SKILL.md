---
name: image-eye
description: "See the contents of LOCAL image files (screenshots, photos, renders saved under /tmp or /opt/data) — describe them, transcribe their text (OCR), and answer questions about them. Use whenever you have an image FILE PATH and need to know what is in it: images downloaded from channel history, generated images, files on disk. Never say you cannot do OCR or image analysis — run this instead."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [image, see, look, view, eye, vision, ocr, screenshot, photo, picture, describe, read image, whats in, transcribe, analyse image, analyze image, gambar, lihat, baca gambar]
    related_skills: [channel-summarizer, document-reader]
---

# Image Eye — view local image files

You CAN see images. When you have a local image file path (PNG, JPG, GIF,
WEBP), run the pre-installed script and read its output — a detailed
description with any visible text transcribed verbatim:

```bash
python3 /opt/data/custom-skills/media/image-eye/describe_image.py <image_path>
```

Ask it a specific question for a focused answer:

```bash
python3 /opt/data/custom-skills/media/image-eye/describe_image.py <image_path> what deadline is shown in this screenshot
```

**Zero dependencies — NEVER pip install anything for this. NEVER claim you
are "missing the required libraries" for OCR or image analysis.**

## When to use

- After `channel-summarizer` saves images from history
  (`/tmp/hermes_gen_slackfile_*`) and the user asks what is in them:
  "what's the context of this uploaded image?", "what does that screenshot
  say?", "lihat gambar di atas"
- Any time you have an image path on disk and need its contents

## How to answer

Run the script per image (newest first, usually only the relevant one or
two), then answer the user's actual question from the description — do not
paste the whole raw description unless asked. Mention you looked at the
image.

## Error handling

- `ANTHROPIC_API_KEY not found` → report: the eye script can't find the API
  key; ask the admin to check /opt/data/custom-.env
- `image is X MB (limit ~4.8MB)` → say the image is too large to analyse and
  ask for a smaller version
- Unsupported type → only PNG/JPG/GIF/WEBP; for PDFs use the document-reader
  skill instead
