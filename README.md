# rdv-prefecture-bot

A Python script that monitors a French prefecture online booking page for newly
released RDV (appointment) slots. It solves the CAPTCHAs that gate access to
the slot-picker, and sounds an audio alarm as soon as a slot appears so a
human can log in and complete the booking manually.

---

## The problem

Non-EU residents in France need prefecture appointments for residence permits,
renewals, and similar procedures. These appointments are booked through
`rdv-prefecture.interieur.gouv.fr`. For the Lyon prefecture and many others,
newly released slots are claimed within seconds of going live — often by
third-party automation acting on behalf of paying clients. Manual refreshing
of the site, even several times per hour, effectively never succeeds.

This is a real access problem for anyone without legal assistance or the
budget for a paid slot-hunting service.

## The approach

The script:

1. Opens the target booking page with **`undetected_chromedriver`** to bypass
   the site's basic bot detection.
2. Runs an inner **state-machine loop** that classifies the current page as one
   of four states:
   - terminal "no slots available" message → log and re-queue
   - reCAPTCHA checkbox → solve via DeathByCaptcha API, submit, re-analyze
   - image CAPTCHA → screenshot, send to DeathByCaptcha for OCR, submit
   - none of the above → assume slots are available, raise to the alarm path
3. On success, raises `SystemExit` to break out of the nested loops and starts
   an infinite audio-alarm loop (`paplay`) until the user kills the process.
4. Between attempts, sleeps a **randomized** 4–6 minutes so the request cadence
   isn't perfectly periodic.

The inner state-machine pattern works because the prefecture site chains
multiple CAPTCHA pages in some flows. Solving one and re-submitting lands you
on a different gate, which the next loop iteration classifies and handles.

## What actually worked

Ran against the Lyon prefecture (`demarche/9040/`) across late October and
early November 2025. The script detected a freed slot, the alarm woke me up,
and I completed the booking manually. One working RDV — which is what I needed.

## What's intentionally simple

This is a practical script, not a polished product. Specifically:

- One file, ~150 lines. No class hierarchy.
- State detection is selector-based. If the prefecture site is redesigned, the
  selectors at the top of the file need updating. Nothing else should need to
  change.
- No persistent logging — stdout only.
- No notification channel other than local audio. Remote monitoring would need
  a Telegram / email hook; that was outside the scope of my need at the time.
- The `SystemExit`-as-break pattern is unusual. It's there because I wanted a
  clean way to exit both the inner state-machine and the outer polling loop at
  the same time, without a shared flag variable. There are more elegant ways;
  this one was the fastest to reason about.

## Stack

- Python 3.11+
- `undetected-chromedriver` (Selenium wrapper with bot-detection evasion)
- `selenium`
- `deathbycaptcha-official` (paid CAPTCHA-solving service; ~$1.39 per 1000
  reCAPTCHA solves at time of use)
- `paplay` (PulseAudio, comes with most Linux desktops)

## Running it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your DeathByCaptcha credentials and target URL

# make sure you have an alarm.mp3 file in the working directory,
# or point ALARM_FILE at a different file

python rdv_bot.py
```

The Chrome major version is set via `CHROME_VERSION_MAIN` in `.env`. Match it
to whatever Chrome/Chromium is installed on the machine — otherwise
`undetected_chromedriver` will print a mismatch warning.

## A note on legality and ethics

This script automates access to a public booking system that is, in practice,
inaccessible to humans without automation — because other automation has
already captured the slots.

I don't think that excuses anything automatically, so a clear position:

- The script uses the same per-attempt cadence a dedicated human would, with
  a 4–6 minute gap between attempts and random jitter. It doesn't hammer the
  site.
- It solves CAPTCHAs via a paid third-party service, which is the same
  mechanism used by every commercial slot-hunting service. The moral weight
  of that is the same whether an individual does it or a business does.
- I believe the root problem is the booking system's design (instant
  depletion, no queue, no priority mechanism), not individual users reaching
  for the only tool that makes the system usable.
- If you use this against a site that has added a real queue or fair-access
  mechanism, don't. At that point you'd be breaking something that works.

## License

MIT — see [LICENSE](LICENSE).

## Author

Built while preparing my reconversion toward software development. Constructed
iteratively, partly with AI-assisted exploration of the CAPTCHA handling and
state-machine structure, debugged against the real target site until it worked.
