# Profile maintenance

The palette uses orange, plum, and parchment.

## Update the profile

The README contains a compact header and automatically refreshed data panels. Edit `scripts/profile.py` for colors, panels, and animations.

Use Python 3.10 or newer and an authenticated GitHub CLI:

```sh
python scripts/profile.py --refresh --check
python -m unittest discover -s tests
```

Use `python scripts/profile.py --build --check` to rebuild static visuals offline.

The generator uses the Python standard library and GitHub CLI. It requires no package installation, third-party widget account, or additional secret. Network requests are limited to GitHub for public profile data. There are no tracking pixels or visitor counters.

## Automatic updates

The Profile assets workflow validates pushes and pull requests. A daily run at 06:17 UTC refreshes the panels. It can also be run manually from Actions.

The refresh job uses the repository's built-in token with contents write permission. Publication uses GitHub's existing authenticated identity without configuring a Git identity. It publishes only changed SVG assets, creates no branches, and refuses to overwrite a newer main branch. Failed fetching or validation leaves the published assets intact.

## Data definitions

Repository totals, language bytes, and update dates cover public original repositories owned by the profile account. Forks and this profile repository are excluded. Archived original projects remain included. Pagination supports more than 100 repositories.

Contributions come from the unauthenticated public GitHub calendar. Any anonymized private contribution counts deliberately made public remain visible, as on the native profile. No private repository content, personal names, contact details, commit messages, credentials, or raw API responses are stored.

Streaks cover the displayed year window rather than all-time history. Dates and refresh timestamps use UTC. Source-byte percentages are rounded independently and can sum slightly above or below 100%.

GitHub's public calendar HTML is an upstream dependency. If its markup changes, strict parsing fails instead of publishing incomplete statistics. Inspect the workflow and adjust `CalendarParser` before refreshing.

## Rendering

The profile uses Markdown and theme-aware pictures. The header adapts to narrow screens. Data panels wrap into a single column.

SVG assets use native shapes, system fonts, and CSS animations. They contain no scripts, external resources, or foreignObject elements. Reduced-motion preferences disable every animation. Image descriptions remain available.

Animations include a subtle header glow, fading overview values, language-bar reveals, rising activity bars, fading repository names, and a contribution fox that consumes active blocks. Blocks reset at the start of each loop. Reduced-motion mode shows the original calendar.

## References

- [Profile formatting and theme-aware images](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/quickstart-for-writing-on-github)
- [Contribution rules](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions)
- [Repository API](https://docs.github.com/en/rest/repos/repos)
- [Actions automatic token](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
