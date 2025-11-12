# Quick Start Guide - Hero Video Background

## ✅ Implementation Complete!

The video background is now fully implemented in your Hero section with:
- Professional video player with autoplay and loop
- Multiple format support (WebM + MP4)
- Poster image fallback
- Mobile optimization and lazy loading
- Accessibility support (respects reduced motion preferences)
- Automatic pause/resume on page visibility
- Gradient overlay for text readability
- Error handling and graceful degradation

## 🎯 What You Need To Do

### Step 1: Get Your Video
Choose ONE of these options:

#### Option A: Use Stock Footage (Recommended for Quick Start)
Visit these free stock video sites:
1. **Pexels Videos**: https://www.pexels.com/videos/
   - Search: "bakery production", "baking", "abstract gradient"
   - Download: HD (1920x1080) or Full HD

2. **Pixabay**: https://pixabay.com/videos/
   - Search: "bakery", "production line", "technology background"
   - Download: 1920x1080 resolution

3. **Coverr**: https://coverr.co/
   - Browse: Food, Business, Abstract categories
   - Download: Free for commercial use

#### Option B: Create Custom Video
- Shoot footage of your bakery operations
- Or hire a videographer
- Or use motion graphics software (After Effects, Blender)

### Step 2: Optimize Your Video
Use **HandBrake** (free): https://handbrake.fr/

**Settings:**
1. Open your video in HandBrake
2. Preset: Choose "Web > Discord Nitro Large 3-6 Minutes 1080p30"
3. Dimensions: 1920x1080 (or 1280x720 for smaller size)
4. Video Codec: H.264 (x264)
5. Framerate: Constant 30fps
6. Quality: RF 23-25 (lower = better quality, larger file)
7. Audio: Remove audio track (not needed)
8. Save as: `hero-bg.mp4`

**Target specs:**
- File size: 3-8 MB (10-20 second loop)
- Keep it SHORT - it will loop automatically

### Step 3: Create Poster Image
Take a frame from your video:
1. Open video in VLC or any video player
2. Pause at a good frame (around 2-3 seconds in)
3. Take screenshot
4. Save as: `hero-bg-poster.jpg`
5. Resize to 1920x1080 if needed
6. Compress to under 500 KB

### Step 4: Place Files
Put these files in the `/static/videos/` folder:

```
/static/videos/
  ├── hero-bg.mp4          (Required - 3-8 MB)
  ├── hero-bg-poster.jpg   (Required - <500 KB)
  └── hero-bg.webm         (Optional - for better compression)
```

### Step 5: Test
1. Save your files
2. Refresh your homepage
3. Video should autoplay (muted) and loop
4. If video doesn't appear, check:
   - File names match exactly
   - Files are in `/static/videos/` folder
   - Check browser console for errors (F12)

## 🎨 Recommended Video Styles

### For Bakery Metrics Application:

**Professional Options:**
1. **Bakery in Action**: Production line, baking process, decorating
2. **Abstract Data**: Flowing particles, network connections, data visualization
3. **Smooth Gradients**: Animated color transitions matching your brand
4. **Time-lapse**: Bakery operations sped up (looks dynamic)

**Color Palette to Match:**
- Blues, Purples, Pinks (matches your current gradient)
- Warm tones for bakery feel
- Avoid too much white (text is white)

**Motion Style:**
- Slow, smooth movement
- Not too busy or distracting
- Subtle enough that text remains readable

## 🚀 Alternative: Temporary Placeholder

If you don't have a video yet, the site will work fine with:
- The gradient background (current fallback)
- The animated accent elements
- Everything will function normally

Once you add the video files, it will automatically appear!

## 📱 Mobile Behavior

The video is optimized for mobile:
- Smaller file size preferred
- Lazy loads when hero section is in view
- Automatically pauses when page is hidden
- Falls back to gradient on slow connections
- Respects user's "reduce motion" accessibility setting

## 🎓 Example Search Terms for Stock Footage

- "bakery production line 4k"
- "abstract gradient background"
- "food production time lapse"
- "data visualization abstract"
- "smooth gradient motion"
- "professional bakery kitchen"
- "technology background loop"

## ⚡ Performance Notes

The implementation includes:
- ✅ Automatic detection of slow connections
- ✅ Mobile data saving (lazy load)
- ✅ Accessibility (reduced motion support)
- ✅ Resource management (pause on tab switch)
- ✅ Error handling (graceful fallback)

## 🆘 Troubleshooting

**Video not showing?**
- Check file path and names
- Look at browser console (F12) for errors
- Verify video format is H.264 MP4
- Try a smaller file size

**Video too slow to load?**
- Compress more in HandBrake (higher RF number)
- Use shorter clip (10 seconds instead of 20)
- Lower resolution to 1280x720

**Video affects site performance?**
- File too large - compress more
- Check video codec is H.264 (not H.265)
- Consider removing WebM version

## 💡 Pro Tips

1. **Keep it short**: 10-15 seconds is perfect for loops
2. **Seamless loops**: Start and end frames should match
3. **Test on mobile**: Most users will be on phones
4. **Check in different browsers**: Chrome, Safari, Firefox
5. **Monitor file size**: Larger files = slower loading

---

**Ready to go!** Just add your video files and refresh the page. Everything else is already set up! 🎉
