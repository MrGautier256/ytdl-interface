**English** · [Français](README.fr.md)

# YTDL Interface

A full-featured graphical interface for [yt-dlp](https://github.com/yt-dlp/yt-dlp), the actively maintained successor to youtube-dl. Works with YouTube and 1000+ other sites.

## Getting started

**Ready-to-run build (recommended):** download the latest `YTDL-Interface.zip` from the [Releases](../../releases) page, extract it anywhere, and run `YTDL-Interface.exe` inside the extracted folder. No install, no prerequisites.

**From source:** double-click `main.pyw` (requires Python 3 with Tkinter, included by default on Windows).

Either way, if yt-dlp and/or ffmpeg are missing on the machine, the app detects it on startup and offers an install window with a per-component progress bar; installation runs in the background without closing the app. Also reachable any time from the Advanced tab ("Download yt-dlp" / "Install ffmpeg" / "Update yt-dlp"). Settings and binaries are stored inside that same folder (`settings.json`, `bin/`), next to the executable, not in a system directory — keep the whole folder together.

## Language and theme

At the top of the window:
- **Language**: 9 languages available (French, English, Spanish, German, Italian, Portuguese, Dutch, Polish, Russian). "Auto" follows the Windows UI language.
- **Theme**: light or dark (modern Sun Valley skin, sv-ttk library bundled in `vendor/`). "Auto" follows the Windows theme, including the title bar.

## Quick start

1. Paste one or more links (one per line) in the **Download** tab.
2. Pick a preset (1080p MP4 video, MP3 audio...) or fine-tune in the other tabs.
3. Click **Download**. The queue shows progress, speed and time remaining.

The **Analyze video** button shows title, duration, thumbnail and the full list of available formats; you can manually pick a specific video format + audio format from there.

## The tabs

- **Download**: links, destination, presets, download queue.
- **Format and quality**: video/audio-only, max resolution, container (mp4/mkv/webm), codec, audio format (mp3, m4a, opus, flac...), quality, custom `-f` selector.
- **Subtitles**: official or auto-generated, languages, srt conversion, embedding.
- **Playlist and filters**: whole playlist or single video, item selection, date/size filters, duplicate-skip archive, error tolerance.
- **Files and metadata**: filename template (with subfolders), thumbnail, metadata, chapters, description, split by chapters, SponsorBlock (mark or remove embedded ads).
- **Network and accounts**: rate limit, parallel fragments (speed-up), proxy, IPv4, browser cookies (private or age-restricted videos), credentials.
- **Advanced**: partial download by time sections, concurrent downloads, binary paths, yt-dlp update, simulate mode, free-form arguments, and a live preview of the generated yt-dlp command (copyable).
- **Log**: full yt-dlp output, for troubleshooting.

Every option has an explanatory tooltip on hover.

## Notes

- Settings are saved in `settings.json`, next to the executable (the password is never saved).
- On a YouTube "Sign in to confirm you're not a bot" error: Network and accounts tab, pick your browser under "Use browser cookies".
- Any yt-dlp option not covered by the interface can be passed via "Extra arguments" (Advanced tab).

## Disclaimer

This tool downloads content from third-party sites. Use it in accordance with those sites' terms of service and rights holders' rights (personal use, royalty-free content, or content you own the rights to).

## License and credits

YTDL Interface is distributed under the MIT license (see [LICENSE](LICENSE)).

On first launch, the app downloads for its own operation:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense / public domain)
- [ffmpeg](https://github.com/BtbN/FFmpeg-Builds) (GPL build by BtbN)

The Sun Valley visual theme ([sv-ttk](https://github.com/rdbende/Sun-Valley-ttk-theme), MIT license) is bundled in `vendor/`.
