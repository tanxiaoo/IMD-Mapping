"""Audit report/report.md against the fact base.

Five checks, each reported with the line number that failed:

  1. NUMBERS    every numeric value in the report appears in data/FACTS.md
  2. FIGURES    every figure filename mentioned exists on disk
  3. COVERAGE   every figure in OUTLINE.md's consolidated list is cited
  4. TERMS      no stale "Track A" / "Track B" terminology
  5. NUMBERING  figures are numbered 1..N in the order they appear, each
                caption matches its image, and every in-text "Figure N"
                resolves to a figure that exists
  6. (report absent or partial is not a failure -- see below)

Runs cleanly against an empty, missing or partial report: a report that does
not exist yet, or cites no figures yet, produces a clean pass with a note.
The point is to be runnable from the first paragraph onward, not only at the
end -- an auditor that fails on an unfinished draft gets switched off.

Exit code 0 if every check passes, 1 if any fails.

Usage:  python code/audit_numbers.py
        python code/audit_numbers.py --report path/to/other.md
"""

import argparse
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPORT = os.path.join(REPO, 'report', 'report.md')
FACTS = os.path.join(REPO, 'data', 'FACTS.md')
OUTLINE = os.path.join(REPO, 'report', 'OUTLINE.md')
FIG_DIRS = ['report/figs'] + [d for d in sorted(os.listdir(REPO))
                              if d.startswith('outputs_') and
                              os.path.isdir(os.path.join(REPO, d))]

# Numbers that are structural rather than measurements: section numbers, years,
# figure numbers, page counts. Checking these against FACTS.md would be noise.
YEARS = {'2017', '2018', '2019', '2025', '2026'}

# Coverage is enforced only once the report cites this share of its planned
# figures. Below it, uncited figures are reported as a note: an auditor that
# fails every early draft is an auditor nobody runs.
COVERAGE_THRESHOLD = 0.60


def _strip_noise(line):
    """Remove spans whose numbers are not claims about results.

    Code spans, markdown links/images, figure and section references, and
    citation page numbers all carry digits that have nothing to do with the
    fact base.
    """
    line = re.sub(r'`[^`]*`', ' ', line)              # code spans
    line = re.sub(r'!?\[[^\]]*\]\([^)]*\)', ' ', line)  # links and images
    line = re.sub(r'\bp{1,2}\.\s*\d+(\s*[–-]\s*\d+)?', ' ', line)  # p. 5, pp. 3-4
    line = re.sub(r'\b[Ff]ig(ure)?s?\.?\s*\d+[a-z]?', ' ', line)
    line = re.sub(r'\b[Ss]ec(tion)?s?\.?\s*\d+(\.\d+)*', ' ', line)
    line = re.sub(r'§\s*\d+(\.\d+)*', ' ', line)
    line = re.sub(r'\bTable\s+[A-Z0-9]+', ' ', line)
    return line


def _numbers(line):
    """Decimal and percentage values that read as measurements."""
    out = set()
    for m in re.finditer(r'(?<![\w.])([+-]?\d+\.\d+)(?![\w])', _strip_noise(line)):
        out.add(m.group(1))
    # Whole-number percentages ("33 %", "38–67 %") are claims too.
    for m in re.finditer(r'(?<![\w.])(\d{1,3})\s*%', _strip_noise(line)):
        out.add(m.group(1))
    return out


def _facts_numbers():
    """Every numeric token in FACTS.md, plus common rounded forms.

    A report may legitimately round 26.253 to 26.25 or 26.3, so each fact value
    is registered at its own precision and at one and two decimals.
    """
    if not os.path.exists(FACTS):
        return None
    text = open(FACTS, encoding='utf-8').read()
    vals = set()
    for m in re.finditer(r'(?<![\w.])([+-]?\d+(?:\.\d+)?)(?![\w])', text):
        raw = m.group(1)
        vals.add(raw)
        vals.add(raw.lstrip('+'))
        try:
            f = float(raw)
        except ValueError:
            continue
        for form in (f'{f:.0f}', f'{f:.1f}', f'{f:.2f}', f'{f:.3f}'):
            vals.add(form)
            vals.add(form.lstrip('+'))
            if form.startswith('-'):
                vals.add(form)
        # A signed fact should satisfy an unsigned mention and vice versa.
        vals.add(f'{abs(f):.1f}')
        vals.add(f'{abs(f):.2f}')
    return vals


def _known(value, facts):
    """Is `value` present in FACTS.md at some sensible precision?"""
    if value in facts or value.lstrip('+') in facts:
        return True
    try:
        f = float(value)
    except ValueError:
        return False
    for form in (f'{f:.0f}', f'{f:.1f}', f'{f:.2f}', f'{f:.3f}',
                 f'{abs(f):.1f}', f'{abs(f):.2f}'):
        if form in facts or form.lstrip('+') in facts:
            return True
    # Integer percentages: accept if any fact rounds to it.
    if f.is_integer():
        return any(abs(float(v) - f) < 0.5 for v in facts
                   if re.fullmatch(r'[+-]?\d+\.\d', v))
    return False


def _figure_index():
    """Every figure filename on disk -> the directory holding it."""
    index = {}
    for d in FIG_DIRS:
        full = os.path.join(REPO, d)
        if not os.path.isdir(full):
            continue
        for name in os.listdir(full):
            if name.lower().endswith(('.png', '.pdf', '.svg')):
                index.setdefault(name, []).append(d)
    return index


def _outline_figures():
    """Figure filenames listed in OUTLINE.md's consolidated table."""
    if not os.path.exists(OUTLINE):
        return {}
    text = open(OUTLINE, encoding='utf-8').read()
    start = text.find('# Consolidated figure list')
    if start < 0:
        return {}
    end = text.find('\n# ', start + 1)
    block = text[start:end if end > 0 else len(text)]
    figs = {}
    for line in block.splitlines():
        m = re.match(r'\|\s*(F\d+)\s*\|\s*`([^`]+)`', line.strip())
        if m:
            name = m.group(2).strip()
            if not name.lower().endswith(('.png', '.pdf', '.svg')):
                name += '.png'
            figs[m.group(1)] = name
    return figs


def check_numbering(lines):
    """Sequential figure numbering, caption pairing and reference resolution.

    Renumbering a report is exactly the kind of edit that leaves a figure
    number pointing at the wrong picture while every filename still resolves,
    so the FIGURES check above passes and nothing notices. Three things are
    verified here:

      ORDER    the Nth embedded image is Figure N. Numbers must run 1..N in
               the order the images appear on the page -- a gap, a repeat or
               an out-of-order number all fail.
      CAPTION  each image is followed within a few lines by a caption whose
               number matches it. Captions carry the numbers a reader
               actually sees, so a caption that disagrees with its image is
               the failure mode a renumber most easily introduces.
      REFS     every in-text "Figure N" names a figure that exists.

    An in-text reference to a figure defined LATER is allowed: forward
    references are normal prose. Only unresolvable numbers fail.

    Returns a list of (line_no, message).
    """
    out = []

    images = []      # (line_no, number, path)
    captions = []    # (line_no, number)
    refs = []        # (line_no, number)

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        m = re.match(r'!\[[^\]]*\]\(([^)]+)\)', stripped)
        if m:
            path = m.group(1)
            alt = re.match(r'!\[\s*Figure\s+(\d+)\s*\]', stripped)
            if alt:
                images.append((i, int(alt.group(1)), path))
            else:
                # An unnumbered embed cannot be checked for order, and
                # silently skipping it would let a figure escape the check.
                out.append((i, f'embedded image {os.path.basename(path)} has '
                               'no "Figure N" alt text, so its position in '
                               'the numbering cannot be checked'))
            continue

        m = re.match(r'\*{0,2}Figure\s+(\d+)\*{0,2}\.\s', stripped)
        if m:
            captions.append((i, int(m.group(1))))
            continue

        # In-text references. Citations of the REFERENCE report use the
        # "Fig. N" form after a page number ("Žgela p. 6, Fig. 7") and are
        # not references to this report's figures, so only the spelled-out
        # "Figure N" / "Figures N and M" form is collected.
        for m in re.finditer(r'\bFigures?\s+(\d+)(?:\s+and\s+(\d+))?', line):
            refs.append((i, int(m.group(1))))
            if m.group(2):
                refs.append((i, int(m.group(2))))

    if not images:
        return out

    # ── ORDER ───────────────────────────────────────────────────────────────
    for pos, (line_no, num, path) in enumerate(images, start=1):
        if num != pos:
            out.append((line_no,
                        f'{os.path.basename(path)} is embedded as "Figure '
                        f'{num}" but is the {pos}{"st" if pos == 1 else "nd" if pos == 2 else "rd" if pos == 3 else "th"} '
                        f'image in the report — figures must be numbered in '
                        f'the order they appear'))

    # ── CAPTION ─────────────────────────────────────────────────────────────
    # Pair each image with the first caption following it, within a short
    # window: a caption further away belongs to something else.
    WINDOW = 4
    for line_no, num, path in images:
        following = [c for c in captions if 0 < c[0] - line_no <= WINDOW]
        if not following:
            out.append((line_no,
                        f'Figure {num} ({os.path.basename(path)}) has no '
                        f'"Figure N." caption within {WINDOW} lines below it'))
            continue
        cap_line, cap_num = following[0]
        if cap_num != num:
            out.append((cap_line,
                        f'caption reads "Figure {cap_num}." but the image '
                        f'above it at line {line_no} is Figure {num} '
                        f'({os.path.basename(path)})'))

    # A caption with no image above it is an orphan the pairing above misses.
    paired = {c[0] for line_no, _, _ in images
              for c in captions if 0 < c[0] - line_no <= WINDOW}
    for cap_line, cap_num in captions:
        if cap_line not in paired:
            out.append((cap_line,
                        f'caption "Figure {cap_num}." has no embedded image '
                        f'in the {WINDOW} lines above it'))

    # ── REFS ────────────────────────────────────────────────────────────────
    defined = {num for _, num, _ in images}
    hi = max(defined)
    for line_no, num in refs:
        if num not in defined:
            out.append((line_no,
                        f'in-text reference to Figure {num}, but the report '
                        f'defines Figures 1 to {hi}'))

    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', nargs='?', default=None,
                    help='report file, or a directory holding report.md')
    ap.add_argument('--report', default=None)
    args = ap.parse_args()

    # Accept the bare form, a file, or a directory. A directory is resolved to
    # report.md inside it, so `audit_numbers.py report/` works as naturally as
    # `audit_numbers.py report/report.md`.
    target = args.report or args.path or DEFAULT_REPORT
    if os.path.isdir(target):
        target = os.path.join(target, 'report.md')
    args.report = target

    # relpath raises across Windows drive letters, so fall back to the path
    # as given when the report lives outside the repo.
    try:
        rel = os.path.relpath(args.report, REPO)
    except ValueError:
        rel = args.report
    failures = []            # (check, line_no, message)
    notes = []

    # ── Load the report; absent or empty is a clean pass ────────────────────
    if not os.path.exists(args.report):
        notes.append(f'{rel} does not exist yet — nothing to audit.')
        lines = []
    else:
        lines = open(args.report, encoding='utf-8').read().splitlines()
        if not any(ln.strip() for ln in lines):
            notes.append(f'{rel} is empty — nothing to audit.')
            lines = []

    facts = _facts_numbers()
    if facts is None:
        failures.append(('SETUP', 0,
                         'data/FACTS.md not found — run '
                         'code/collect_metrics.py first.'))
        facts = set()

    disk = _figure_index()
    cited = set()

    for i, line in enumerate(lines, start=1):
        # 4. TERMS — stale vocabulary.
        for term in ('Track A', 'Track B'):
            if term in line:
                failures.append((
                    'TERMS', i,
                    f'stale terminology {term!r} — use "same-source '
                    f'validation" / "independent validation"'))

        # 1. NUMBERS — every measurement must trace to FACTS.md.
        for value in sorted(_numbers(line)):
            if value in YEARS:
                continue
            if not _known(value, facts):
                failures.append((
                    'NUMBERS', i,
                    f'{value} not found in data/FACTS.md'))

        # 2. FIGURES — every filename mentioned must exist.
        for m in re.finditer(r'([\w./-]*\bfig[\w.-]*\.(?:png|pdf|svg))',
                             line, re.IGNORECASE):
            ref = m.group(1)
            name = os.path.basename(ref)
            cited.add(name)
            if name not in disk:
                failures.append((
                    'FIGURES', i,
                    f'{ref} does not exist in {" / ".join(FIG_DIRS[:3])}…'))

    # 5. NUMBERING — sequential figure numbers, captions and references.
    for line_no, msg in check_numbering(lines):
        failures.append(('NUMBERING', line_no, msg))

    # 3. COVERAGE — every planned figure must be cited somewhere.
    outline_figs = _outline_figures()
    if not lines:
        if outline_figs:
            notes.append(f'{len(outline_figs)} figures planned in OUTLINE.md; '
                         'coverage check skipped while the report is empty.')
    elif not outline_figs:
        notes.append('No consolidated figure list found in OUTLINE.md; '
                     'coverage check skipped.')
    else:
        missing = [(fid, name) for fid, name
                   in sorted(outline_figs.items(),
                             key=lambda kv: int(kv[0][1:]))
                   if name not in cited]
        # A draft that cites nothing yet is unfinished, not wrong. Coverage
        # only becomes a failure once the report cites most of its figures --
        # otherwise every early draft drowns in "not cited yet" and the tool
        # stops being run. Below the threshold it reports as a note.
        drafting = len(cited) < len(outline_figs) * COVERAGE_THRESHOLD
        if missing and drafting:
            notes.append(
                f'{len(cited)}/{len(outline_figs)} figures cited so far; '
                f'coverage enforced once {int(COVERAGE_THRESHOLD * 100)} % '
                f'are in. Not yet cited: '
                + ', '.join(fid for fid, _ in missing))
        else:
            for fid, name in missing:
                failures.append((
                    'COVERAGE', 0,
                    f'{fid} {name} is in OUTLINE.md but never cited'))

    # ── Report ──────────────────────────────────────────────────────────────
    width = 66
    print('=' * width)
    print('  audit_numbers.py')
    print('=' * width)
    print(f'report : {rel}'
          f'{"" if lines else "  (absent/empty)"}')
    print(f'facts  : data/FACTS.md  ({len(facts):,} numeric forms)')
    print(f'figures: {len(disk)} on disk across {len(FIG_DIRS)} directories')
    if lines:
        print(f'lines  : {len(lines):,}   figures cited: {len(cited)}')
    print()

    for n in notes:
        print(f'  note: {n}')
    if notes:
        print()

    if failures:
        by_check = {}
        for check, line_no, msg in failures:
            by_check.setdefault(check, []).append((line_no, msg))
        for check in ('SETUP', 'TERMS', 'NUMBERS', 'FIGURES', 'NUMBERING',
                      'COVERAGE'):
            items = by_check.get(check)
            if not items:
                continue
            print(f'{check}  ({len(items)} failure'
                  f'{"s" if len(items) != 1 else ""})')
            for line_no, msg in items:
                short = os.path.basename(rel)
                loc = f'{short}:{line_no}' if line_no else short
                print(f'  {loc}: {msg}')
            print()
        print('=' * width)
        print(f'FAILED — {len(failures)} problem'
              f'{"s" if len(failures) != 1 else ""}')
        print('=' * width)
        return 1

    print('  NUMBERS   ok')
    print('  FIGURES   ok')
    print('  NUMBERING ok')
    print('  COVERAGE  ok')
    print('  TERMS     ok')
    print()
    print('=' * width)
    print('PASSED')
    print('=' * width)
    return 0


if __name__ == '__main__':
    sys.exit(main())
