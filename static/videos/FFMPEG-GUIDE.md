# Advanced Video Optimization with FFmpeg

If you're comfortable with command-line tools, FFmpeg provides the best compression and control.

## Install FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from: https://ffmpeg.org/download.html

**Linux:**
```bash
sudo apt-get install ffmpeg
```

## Basic Compression Commands

### Convert and Compress to MP4 (H.264)
```bash
ffmpeg -i input.mov -c:v libx264 -preset slow -crf 23 -vf "scale=1920:1080" -r 30 -an -movflags +faststart hero-bg.mp4
```

**Explanation:**
- `-i input.mov`: Your source video file
- `-c:v libx264`: Use H.264 codec
- `-preset slow`: Better compression (use 'medium' for faster encoding)
- `-crf 23`: Quality (18=high quality, 28=lower quality, 23=balanced)
- `-vf "scale=1920:1080"`: Resize to Full HD
- `-r 30`: Set framerate to 30fps
- `-an`: Remove audio track
- `-movflags +faststart`: Optimize for web streaming
- `hero-bg.mp4`: Output filename

### Create HD Version (720p) for Smaller File Size
```bash
ffmpeg -i input.mov -c:v libx264 -preset slow -crf 25 -vf "scale=1280:720" -r 24 -an -movflags +faststart hero-bg.mp4
```

### Create WebM Version (Better Compression)
```bash
ffmpeg -i input.mov -c:v libvpx-vp9 -crf 30 -b:v 0 -vf "scale=1920:1080" -r 30 -an hero-bg.webm
```

## Trim Video to Create Short Loop

### Trim to 15 seconds
```bash
ffmpeg -i input.mp4 -ss 00:00:00 -t 00:00:15 -c:v libx264 -preset slow -crf 23 -an -movflags +faststart hero-bg.mp4
```

**Explanation:**
- `-ss 00:00:00`: Start time (hours:minutes:seconds)
- `-t 00:00:15`: Duration (15 seconds)

### Create Seamless Loop
Extract a segment that loops well:
```bash
# Find a good loop point in your video, then:
ffmpeg -i input.mp4 -ss 00:00:05 -t 00:00:12 -c:v libx264 -preset slow -crf 23 -vf "scale=1920:1080" -r 30 -an -movflags +faststart hero-bg.mp4
```

## Adjust Video Brightness/Contrast

### Darken Video (Better for Text Overlay)
```bash
ffmpeg -i input.mp4 -vf "eq=brightness=-0.1:contrast=1.1,scale=1920:1080" -c:v libx264 -preset slow -crf 23 -r 30 -an -movflags +faststart hero-bg.mp4
```

### Apply Color Grading
```bash
# Cooler tones (blue/purple to match your brand)
ffmpeg -i input.mp4 -vf "colorbalance=rs=-0.1:gs=0:bs=0.1:rm=-0.1:gm=0:bm=0.1,scale=1920:1080" -c:v libx264 -preset slow -crf 23 -r 30 -an -movflags +faststart hero-bg.mp4
```

## Create Poster Image from Video

### Extract Frame at 3 seconds
```bash
ffmpeg -i hero-bg.mp4 -ss 00:00:03 -vframes 1 -vf "scale=1920:1080" hero-bg-poster.jpg
```

### Compress Poster Image
```bash
ffmpeg -i hero-bg-poster.jpg -q:v 5 -vf "scale=1920:1080" hero-bg-poster-compressed.jpg
```

## Batch Processing

### Process Multiple Videos
```bash
for file in *.mov; do
    ffmpeg -i "$file" -c:v libx264 -preset slow -crf 23 -vf "scale=1920:1080" -r 30 -an -movflags +faststart "${file%.mov}-compressed.mp4"
done
```

## Quality vs. File Size Guide

**CRF Values (Constant Rate Factor):**
- `18`: Very high quality (~10-15 MB for 15 seconds)
- `23`: High quality, good balance (~5-8 MB) ⭐ **Recommended**
- `26`: Good quality, smaller file (~3-5 MB)
- `28`: Acceptable quality, small file (~2-3 MB)
- `30+`: Lower quality, very small (~1-2 MB)

**Resolution Options:**
- `3840x2160` (4K): Overkill for web, very large files
- `1920x1080` (Full HD): Perfect for desktop ⭐ **Recommended**
- `1280x720` (HD): Good balance for mobile
- `1024x576`: Acceptable, small file size

## Target Specifications Recap

**Recommended Settings:**
```bash
# Perfect balance for web
ffmpeg -i input.mov \
  -c:v libx264 \
  -preset slow \
  -crf 23 \
  -vf "scale=1920:1080" \
  -r 30 \
  -an \
  -movflags +faststart \
  hero-bg.mp4
```

**Expected Results:**
- File Size: 3-8 MB for 10-20 seconds
- Resolution: 1920x1080
- Bitrate: ~2-4 Mbps
- Format: H.264 MP4
- Framerate: 30fps

## Check Video Information

```bash
ffmpeg -i hero-bg.mp4
```

This will show:
- Duration
- Resolution
- Bitrate
- Codec
- File size

## Create Both MP4 and WebM

```bash
# Create MP4
ffmpeg -i input.mov -c:v libx264 -preset slow -crf 23 -vf "scale=1920:1080" -r 30 -an -movflags +faststart hero-bg.mp4

# Create WebM from MP4
ffmpeg -i hero-bg.mp4 -c:v libvpx-vp9 -crf 30 -b:v 0 -vf "scale=1920:1080" -r 30 -an hero-bg.webm
```

## Troubleshooting

**Video too large?**
- Increase CRF value: `-crf 26` or `-crf 28`
- Lower resolution: `-vf "scale=1280:720"`
- Reduce framerate: `-r 24`
- Shorten duration: `-t 00:00:10`

**Video too dark/bright?**
```bash
# Adjust brightness/contrast
ffmpeg -i input.mp4 -vf "eq=brightness=0.1:contrast=1.2" output.mp4
```

**Video jerky or stuttering?**
- Ensure constant framerate: `-r 30`
- Add faststart flag: `-movflags +faststart`
- Use slower preset: `-preset slow`

**Browser won't play video?**
- Ensure H.264 codec: `-c:v libx264`
- Check no audio track: `-an`
- Verify MP4 container

## Pro Tips

1. **Always use `-movflags +faststart`** for web videos (enables progressive playback)
2. **Remove audio** with `-an` to reduce file size
3. **Test different CRF values** to find best quality/size balance
4. **Use preset 'slow'** for better compression (takes longer but worth it)
5. **Create both MP4 and WebM** for best browser compatibility

---

**Need help?** Check FFmpeg documentation: https://ffmpeg.org/ffmpeg.html
