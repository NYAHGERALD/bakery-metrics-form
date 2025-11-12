# Hero Video Background Assets

## Required Files

Place your video files in this directory:

### Primary Video (Required)
- **Filename:** `hero-bg.mp4`
- **Format:** MP4 (H.264 codec)
- **Resolution:** 1920x1080 (Full HD) or 1280x720 (HD)
- **Duration:** 10-20 seconds (will loop automatically)
- **File Size:** 3-8 MB maximum
- **Frame Rate:** 24-30 fps
- **Audio:** Muted/No audio

### Optional WebM Version (Better Compression)
- **Filename:** `hero-bg.webm`
- **Format:** WebM (VP9 codec)
- **Same specs as MP4 above**

### Poster Image (Fallback/Loading State)
- **Filename:** `hero-bg-poster.jpg`
- **Format:** JPG or PNG
- **Resolution:** 1920x1080
- **File Size:** < 500 KB

## Video Content Recommendations

1. **Bakery Operations:** Baking process, decorating, production lines
2. **Abstract Motion:** Smooth gradients, particle effects, data visualizations
3. **Professional Imagery:** Clean, modern, warm color tones
4. **Subtle Movement:** Not too distracting, maintains text readability

## Free Video Resources

If you need stock footage:
- **Pexels Videos:** https://www.pexels.com/videos/
- **Pixabay Videos:** https://pixabay.com/videos/
- **Coverr:** https://coverr.co/

Search terms: "bakery", "production", "abstract motion", "gradient background", "technology"

## Video Compression Tools

To optimize your video file size:
- **HandBrake:** https://handbrake.fr/ (Free, cross-platform)
- **FFmpeg:** Command-line tool for advanced users
- **CloudConvert:** https://cloudconvert.com/mp4-converter (Online)

### Recommended HandBrake Settings:
- Preset: Web > Discord Nitro Large 3-6 Minutes 1080p30
- Video Codec: H.264
- Framerate: 30 fps (constant)
- Quality: RF 23-26
- Audio: None (remove audio track)

## Implementation Status

✅ Video background code implemented in `templates/index.html`
⏳ Waiting for video assets to be placed in this directory

Once you add the video files, refresh the homepage to see them in action!
