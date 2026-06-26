# Car Logger — Product Definition

## Register
**Product (dashboard / tool / utility)**  
This is a web-based surveillance and logging surface first — not a marketing site or brand showcase. Every design decision serves the core workflow: monitor, detect, read, review.

## One-liner
A real-time car security logger that watches for motion, reads license plates with AI, and gives you a calm dashboard to review everything from your phone.

## Target Users
- **Primary:** A car owner (you, in this case) who parks a vehicle with a laptop + webcam inside and wants to know who comes and goes
- **Secondary:** Someone reviewing history — "was my car here at 3am?", "what plates have I seen this week?"

## Core Workflows
1. **Monitor** — glance at the live feed; see status (active/idle/watching) and recent detections
2. **Review** — browse detection history; search by plate, date, or location
3. **Configure** — tune sensitivity, set detection zone, enter API key, pick location source

## Emotional Goal
**Calm alertness + peace of mind.**  
The dashboard should feel quietly capable — like a security camera feed that's always recording but doesn't demand attention until something happens. When it alerts, the information should be immediate and trustworthy.

## Strategic Principles
1. **Reliability first** — the system runs unattended for hours; it must reconnect after camera failures, survive API errors, and never lose a detection
2. **Glanceable** — the dashboard works on a phone screen; key info (status, recent plates, count) must be readable in under 2 seconds
3. **Zero-config operation** — install once, launch, and the system runs; configuration is optional tuning, not required setup
4. **Privacy-conscious** — data stays local (SQLite); the only external call is the AI plate reader (opt-in, configurable)

## Anti-References
- **Not** dated surveillance DVR/NVR software (beige menus, wrinkle-free gradients, 2000s security UI)
- **Not** hacker/cyber aesthetic (green-on-black, matrix rain, "cyberpunk surveillance" tropes)
- **Not** corporate ops dashboards (Grafana-style metric overload, uptime graphs, sparklines)

## Visual Tone
- **Atmosphere:** Dark, quiet, spacious — like a well-lit room at night
- **Color:** Cool neutrals with restrained accent colors; nothing that screams for attention when idle
- **Motion:** Subtle transitions and micro-interactions; nothing that distracts from the feed
- **Typography:** Clean, readable, mono for data (plates, timestamps)
