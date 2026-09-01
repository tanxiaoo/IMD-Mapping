"""Audit report/report.tex against the fact base.

Six checks, each reported with the line number that failed:

  1. NUMBERS    every numeric value in the report appears in data/FACTS.md
  2. FIGURES    every figure filename mentioned exists on disk
  3. COVERAGE   every figure in OUTLINE.md's consolidated list is cited
  4. TERMS      no stale "Track A" / "Track B" terminology
  5. LABELS     every \\label is defined exactly once, every \\ref resolves to a
                defined label, and no label is left unused
  6. CITATIONS  every [N] citation resolves to a References entry, and every
                entry is cited at least once

The report is LaTeX. Markdown is still accepted -- `--report x.md` works and
the source format is detected from the extension -- because report.md is kept
in the repo until the conversion is verified, and an auditor that could only
read one of the two would be useless for comparing them.

Two LaTeX details drive the NUMBERS check and neither is optional:

  ESCAPED PERCENT   LaTeX writes a literal percent sign as `\\%`, so every
                    "33 %" in the markdown became "33\\,\\%" in the .tex. A
                    percentage regex written for markdown still matches the
                    digits but the backslash breaks the `\\s*%` tail, so every
                    percentage claim silently stops being checked while the
                    check still reports "ok". The percent pattern below
                    therefore accepts an optional `\\,`/`~`/`\\;` spacer and a
                    backslash before the sign.
  MATHS MINUS       Signed values are set in maths mode as `$-0.070$`, and
                    siunitx table cells carry a bare `-0.070`. Both must read
                    as the negative number they print, so `$` and the maths
                    delimiters are stripped before numbers are extracted.

Runs cleanly against an empty, missing or partial report: a report that does
not exist yet, or cites no figures yet, produces a clean pass with a note.
The point is to be runnable from the first paragraph onward, not only at the
end -- an auditor that fails on an unfinished draft gets switched off.

Exit code 0 if every check passes, 1 if any fails.

Usage:  python code/audit_numbers.py
        python code/audit_numbers.py report/
        python code/audit_numbers.py --report path/to/other.tex
"""

import argparse
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPORT = os.path.join(REPO, 'report', 'report.tex')
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


def _is_tex(path):
    return str(path).lower().endswith('.tex')


def _strip_noise(line):
    """Remove spans whose numbers are not claims about results.

    Verbatim spans, markdown links/images, figure and section references, and
    citation page numbers all carry digits that have nothing to do with the
    fact base. The LaTeX cases are the additions: \\includegraphics paths carry
    a run directory full of digits (p10p25p50p75p90), \\label/\\ref keys and
    \\url targets carry digits that are identifiers rather than measurements,
    and siunitx column specs (table-format=2.3) are layout.
    """
    line = re.sub(r'`[^`]*`', ' ', line)              # markdown code spans
    line = re.sub(r'\\(?:texttt|url|href)\{[^}]*\}', ' ', line)
    line = re.sub(r'\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}', ' ', line)
    line = re.sub(r'\\(?:label|ref|Cref|cref|autoref)\{[^}]*\}', ' ', line)
    line = re.sub(r'\\begin\{tabular\}\{[^}]*\}', ' ', line)
    line = re.sub(r'table-format\s*=\s*[-\d.]+', ' ', line)
    line = re.sub(r'!?\[[^\]]*\]\([^)]*\)', ' ', line)  # links and images
    line = re.sub(r'\bpp?\.\s*~?\d+(\s*[–ked-]*\s*\d+)?', ' ', line)  # p. 5, pp.~3--4
    line = re.sub(r'\bpp?\.~?\d+', ' ', line)
    line = re.sub(r'\b[Ff]ig(ure)?s?\.?~?\s*\d+[a-z]?', ' ', line)
    line = re.sub(r'\b[Ss]ec(tion)?s?\.?\s*\d+(\.\d+)*', ' ', line)
    line = re.sub(r'§\s*\d+(\.\d+)*', ' ', line)
    line = re.sub(r'\bTable\s+[A-Z0-9]+', ' ', line)
    return line


# LaTeX writes a literal percent as `\%`, usually after a thin space: `33\,\%`.
# Matching only `\d\s*%` would skip every one of them and report a clean pass
# over a check that examined nothing, so the spacer and the backslash are part
# of the pattern. The markdown form ("33 %") still matches the same regex.
_PCT = re.compile(r'(?<![\w.])(\d{1,3})\s*(?:\\[,;:! ]|~)?\s*\\?%')

# Signed values reach the .tex two ways: `$-0.070$` in prose, and a bare
# `-0.070` inside an S column. Stripping the maths delimiters lets one number
# pattern read both.
_MATHS = re.compile(r'[$]|\\(?:mathrm|textbf|textit|text)\b')


def _numbers(line):
    """Decimal and percentage values that read as measurements."""
    out = set()
    clean = _MATHS.sub(' ', _strip_noise(line))
    for m in re.finditer(r'(?<![\w.])([+-]?\d+\.\d+)(?![\w])', clean):
        out.add(m.group(1))
    # Whole-number percentages ("33 %", "33\,\%", "38 to 67\,\%") are claims too.
    for m in _PCT.finditer(clean):
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
    # Integer percentages: accept if any fact rounds to it. This is a weak
    # test and known to be one -- across ~2,400 fact forms most two-digit
    # integers find some fact that rounds to them, so a wrong whole-number
    # percentage can pass. It is kept as-is because tightening it would
    # reject legitimate rounding ("a reduction of 33 %" for 33.0), but it
    # means the NUMBERS check is strong on decimals and weak on bare
    # integers. Decimal percentages ("33.0 %") get the full precision test.
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


def check_labels(lines):
    """Every label defined once, every ref resolves, no label unused.

    This replaces the sequential-numbering check the markdown report needed.
    LaTeX assigns the numbers, so a figure can no longer be numbered wrongly;
    what can go wrong instead is the binding between a label and the float it
    names. Three failures matter and none is visible to the other checks:

      DUPLICATE  the same \\label defined in two floats. LaTeX resolves every
                 \\ref of it to whichever came last and only warns, so a
                 reference silently points at the wrong table.
      DANGLING   a \\ref naming a label nothing defines. It typesets as `??`,
                 which is easy to miss in a 40-page PDF and impossible to miss
                 here.
      UNUSED     a label no \\ref names. Usually the residue of a cut
                 reference, and the signal that a float has quietly stopped
                 being discussed in the prose.

    Every float is also required to carry both a caption and a label, since a
    float missing either escapes the binding check entirely.

    Returns a list of (line_no, message).
    """
    out = []
    text = '\n'.join(lines)

    # Line number of each character offset, for reporting.
    def line_of(pos):
        return text.count('\n', 0, pos) + 1

    # ── Floats must carry a caption and a label ─────────────────────────────
    defined = {}       # label -> [line_no, ...]
    for env in ('figure', 'table', 'longtable'):
        for m in re.finditer(r'\\begin\{' + env + r'\*?\}(.*?)\\end\{'
                             + env + r'\*?\}', text, re.S):
            body, at = m.group(1), line_of(m.start())
            has_cap = re.search(r'\\caption\{', body)
            lab = re.search(r'\\label\{([^}]+)\}', body)
            if not has_cap:
                out.append((at, f'{env} has no \\caption{{}}'))
            if not lab:
                out.append((at, f'{env} has no \\label{{}}, so nothing can '
                                f'reference it'))

    # ── Every label, wherever defined ───────────────────────────────────────
    for m in re.finditer(r'\\label\{([^}]+)\}', text):
        defined.setdefault(m.group(1).strip(), []).append(line_of(m.start()))

    for lab, where in sorted(defined.items()):
        if len(where) > 1:
            out.append((where[1],
                        f'label {lab!r} is defined {len(where)} times '
                        f'(lines {", ".join(str(w) for w in where)}) — every '
                        f'\\ref to it resolves to the last one'))

    # ── Every reference ─────────────────────────────────────────────────────
    # cleveref's \cref takes a comma-separated list, so each key is split out.
    used = {}
    for m in re.finditer(r'\\(?:auto|C|c)?ref\{([^}]+)\}', text):
        for key in m.group(1).split(','):
            used.setdefault(key.strip(), line_of(m.start()))

    for lab, line_no in sorted(used.items()):
        if lab not in defined:
            out.append((line_no,
                        f'\\ref to {lab!r}, which no \\label defines — this '
                        f'typesets as "??"'))

    for lab, where in sorted(defined.items()):
        if lab not in used:
            out.append((where[0], f'label {lab!r} is never referenced'))

    return out


def _references_line(lines):
    """1-based line of the References heading, markdown or LaTeX."""
    for i, ln in enumerate(lines, start=1):
        s = ln.strip()
        if re.match(r'^#{1,3}\s+References\s*$', s):
            return i
        if re.match(r'^\\(?:section|subsection)\*?\{References\}\s*$', s):
            return i
    return None


def check_citations(lines):
    """Numbered citations resolve, and every reference entry is cited.

    The report cites in the style `[1]`, `[1, p. 5]`, `[1, pp. 3-5, Fig. 3]`,
    against a numbered References section at the end. Two failure modes matter
    and neither is visible to the other checks:

      DANGLING  a citation whose number has no entry -- the reader follows it
                to nothing.
      ORPHAN    an entry nothing cites -- usually a reference left behind when
                the text that needed it was cut.

    Also reports a References section that is absent, or numbered with gaps or
    out of order, since the numbering is what makes a citation resolvable.

    Returns a list of (line_no, message).
    """
    out = []

    start = _references_line(lines)
    body = lines if start is None else lines[:start - 1]
    refs = [] if start is None else lines[start - 1:]

    # Citations in the body only: a bracketed number optionally followed by
    # locators. `[1, p. 5]` and `[12]` both count; `[12] Benjamini...` inside
    # the reference list does not, which is why the body is sliced off first.
    cited = {}
    for i, line in enumerate(body, start=1):
        # Optional-argument brackets are not citations: \begin{figure}[htbp],
        # \includegraphics[width=...], S[table-format=2.3]. Only a bracket
        # holding a bare number plus optional locators counts.
        scrubbed = re.sub(r'\\begin\{[^}]*\}\[[^\]]*\]', ' ', line)
        scrubbed = re.sub(r'\\includegraphics\[[^\]]*\]', ' ', scrubbed)
        scrubbed = re.sub(r'\bS\[[^\]]*\]', ' ', scrubbed)
        scrubbed = re.sub(r'\\usepackage\[[^\]]*\]', ' ', scrubbed)
        for m in re.finditer(r'\[(\d+)(?:,\s*(?:pp?\.|Figs?\.)[^\]]*)?\]',
                             scrubbed):
            cited.setdefault(int(m.group(1)), i)

    if start is None:
        if cited:
            out.append((min(cited.values()),
                        f'{len(cited)} numbered citation(s) but no '
                        'References section to resolve them against'))
        return out

    # Markdown lists entries as "[1] Žgela...", LaTeX as "\item[{[1]}] Žgela...".
    entries = {}
    for off, line in enumerate(refs):
        s = line.strip()
        m = (re.match(r'^\[(\d+)\]', s)
             or re.match(r'^\\item\s*\[\{?\[(\d+)\]\}?\]', s))
        if m:
            entries[int(m.group(1))] = start + off

    if not entries:
        out.append((start, 'References section has no `[N]` entries'))
        return out

    expected = list(range(1, len(entries) + 1))
    if sorted(entries) != expected:
        out.append((start,
                    f'reference numbering is {sorted(entries)}, expected '
                    f'{expected} — entries must run 1..N without gaps'))

    for num, line_no in sorted(cited.items()):
        if num not in entries:
            out.append((line_no,
                        f'citation [{num}] has no entry in the References '
                        f'section'))

    for num, line_no in sorted(entries.items()):
        if num not in cited:
            out.append((line_no,
                        f'reference [{num}] is never cited in the report'))

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
        # report.tex is the source; report.md is kept until the conversion is
        # verified, so fall back to it rather than reporting nothing to audit.
        tex = os.path.join(target, 'report.tex')
        md = os.path.join(target, 'report.md')
        target = tex if os.path.exists(tex) else md
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

    # The References section is bibliography, not results. Its DOIs, arXiv ids,
    # volume/page numbers and years are identifiers that cannot trace to the
    # fact base and must not be checked against it -- 2507.22291 is an arXiv
    # id, not a measurement. Everything before it is checked as normal, and the
    # TERMS and FIGURES checks still run over the whole file.
    refs_from = _references_line(lines)

    for i, line in enumerate(lines, start=1):
        # 4. TERMS — stale vocabulary.
        for term in ('Track A', 'Track B'):
            if term in line:
                failures.append((
                    'TERMS', i,
                    f'stale terminology {term!r} — use "same-source '
                    f'validation" / "independent validation"'))

        # 1. NUMBERS — every measurement must trace to FACTS.md.
        if refs_from is None or i < refs_from:
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

    # 5. LABELS — every label defined once, every ref resolves, none unused.
    if _is_tex(args.report):
        for line_no, msg in check_labels(lines):
            failures.append(('LABELS', line_no, msg))
    elif lines:
        notes.append('LABELS check applies to LaTeX; skipped for a markdown '
                     'report.')

    # 6. CITATIONS — every [N] resolves, every entry is cited.
    for line_no, msg in check_citations(lines):
        failures.append(('CITATIONS', line_no, msg))

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
        for check in ('SETUP', 'TERMS', 'NUMBERS', 'FIGURES', 'LABELS',
                      'CITATIONS', 'COVERAGE'):
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
    print(f'  LABELS    {"ok" if _is_tex(args.report) else "n/a (markdown)"}')
    print('  CITATIONS ok')
    print('  COVERAGE  ok')
    print('  TERMS     ok')
    print()
    print('=' * width)
    print('PASSED')
    print('=' * width)
    return 0


if __name__ == '__main__':
    sys.exit(main())
