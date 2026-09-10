# Hue Session

A Mac app that turns a Logic Pro recording session into a Philips Hue Play lightshow. It listens to digital (or analog) inputs on your SSL interface, analyzes the live audio, and streams colors to Hue Play lights through the Hue Bridge Entertainment API — the same low-latency path Spotify uses.

**Author:** levensailor

## What it does

- Discovers and pairs with a Hue Bridge on your LAN
- Lists Entertainment / Sync areas that include Hue Play bars
- Captures live input from an SSL (or any Core Audio) interface
- Maps bass, mids, highs, beats, and per-channel energy onto the Play lights at ~40 Hz
- Provides a local studio dashboard with meters and light previews

This is a local app. It talks to your bridge and your audio interface on the same Mac. It is not a cloud service.

## Public assets

| Asset | URL | Access |
| --- | --- | --- |
| Studio dashboard | http://127.0.0.1:8742 | Local only. No login. Pair the Hue Bridge once. |

Change the bind address and port with `APP_HOST` and `APP_PORT` in `.env`.

## Requirements

- macOS with Python 3.11+
- Philips Hue Bridge (v2 square or Pro) on the same network
- One or more Hue Play lights in an Entertainment / Sync area
- SSL audio interface (SSL 2, 2+, 12, or similar) used by Logic Pro
- Microphone permission for the terminal or Python runtime

## Setup

```bash
cd hue
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Hue Play area

1. Open the official Hue app.
2. Create an Entertainment / Sync area that includes the Play bars.
3. Place the bars left / right (or left / center / right). The app maps bass to the left and highs to the right.

### Logic Pro + SSL

1. In Logic Pro, set the SSL interface as the audio input and output.
2. Record or monitor as usual.
3. In Hue Session, choose that same SSL device and the channels you are tracking (`0,1` for inputs 1–2; raise the numbers for later analog or digital inputs).
4. If macOS will not let two apps open the SSL inputs at once:
   - Route a Logic send/bus to [BlackHole](https://existential.audio/blackhole/) and select BlackHole here, or
   - Enable loopback in SSL 360 and select those loopback channels.

macOS will prompt for Microphone access the first time capture starts. Allow it under **System Settings → Privacy & Security → Microphone**.

## Run

```bash
source .venv/bin/activate
python -m app
```

Open http://127.0.0.1:8742

1. **Discover** the Hue Bridge (or type its IP).
2. Press the link button on the bridge, then **Pair bridge**.
3. Select the Entertainment area that contains the Play lights.
4. Select the SSL device and input channels.
5. Choose a mode and **Start lightshow**.

Stop Hue Sync, Spotify + Hue, or any other Entertainment stream first. The bridge allows only one streamer at a time.

Credentials stay in `data/credentials.json` on this Mac. They are gitignored.

## Lightshow modes

| Mode | Behavior |
| --- | --- |
| Spectrum | Bass / mid / high across Play bars by position |
| Logic Session | Warmer, less strobe, built for tracking |
| Pulse | Whole-rig energy and pitch |
| Split | Each selected SSL channel drives a light |
| Studio | Amber kick glow |
| Fire / Ocean | Palette variants |

## Configuration

Copy `.env.example` to `.env`. Names, ports, log paths, and Hue pairing identity are all environment variables. Do not hardcode machine-specific values in source.

Logs write to the console and to a rotating file (`logs/hue-session.log`, 1 MB, 3 backups) with America/New_York timestamps, function name, and line number.

## Deployment

This app must run on the Mac that is attached to the SSL interface and on the same LAN as the Hue Bridge. There is nothing to deploy to a public host.

To run it in the background after login, use `launchd` or keep a terminal session with `python -m app`.
