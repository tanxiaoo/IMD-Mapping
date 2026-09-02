"""Build the internal review deck: IMD mapping, Milan / Hanoi / HCMC, 2018.

Audience is the professor and colleagues, technical, familiar with Zgela's
AlphaEarth study. The through-line is that most of the same-source advantage was
agreement with CLMS rather than accuracy: same-source validation is right for
model selection and wrong for claiming accuracy.

    .venv\\Scripts\\python.exe code/make_internal_deck.py

Writes IMD_internal_review.pptx at the repo root.

Two rules this script is built around:

* **report/report.tex is the source of truth.** Every number below is
  transcribed from it, and each table carries the report label it came from so a
  claim can be traced back. Unlike ``make_presentation.py`` this script does not
  read the run CSVs: the report is the checked artefact and re-deriving numbers
  from CSVs would reintroduce the possibility of the deck and the report
  disagreeing.
* **The report figures are used exactly as they are.** Nothing is rebuilt,
  cropped or restyled; ``add_picture`` only scales to fit the content box.

House style (palette, header, textbox, rule, add_picture, table) is imported
from ``make_presentation.py`` at the repo root rather than copied, so the two
decks cannot drift apart.
"""

import os
import sys

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

# make_presentation.py lives at the repo root, not in code/. Import its house
# style rather than restating it. It reads the run metadata at import time
# through relative paths, so the repo root must be both on sys.path and the
# working directory -- chdir here rather than requiring the caller to remember,
# since every path this script uses is absolute anyway.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from make_presentation import (  # noqa: E402
    ACCENT, INK, MUTED, RULE, W, H,
    add_picture, add_slide, header, rule, table, textbox,
)

FIGS = os.path.join(ROOT, 'report', 'figs')
OUT_PPTX = os.path.join(ROOT, 'IMD_internal_review.pptx')

# Content box, matching make_presentation.py.
X0, CW = Inches(0.72), Inches(11.9)


def fig(*parts):
    """Path to a report figure, checked at build time.

    A missing figure must fail loudly: a silently skipped slide in a deck built
    the morning of a meeting is exactly the failure this guards against.
    """
    p = os.path.join(FIGS, *parts)
    if not os.path.exists(p):
        raise FileNotFoundError(f'cited figure missing: {p}')
    return p


# ══════════════════════════════════════════════════════════════════════════════
# Slide furniture beyond the imported helpers
# ══════════════════════════════════════════════════════════════════════════════

def notes(slide, text):
    """Put the spoken argument in the speaker notes.

    The picture talks and the notes carry what is said, so anything longer than
    a single line belongs here rather than on the slide.
    """
    tf = slide.notes_slide.notes_text_frame
    tf.text = text.strip()
    return tf


# Character width of Calibri as a fraction of point size, averaged over mixed
# case prose. Used to predict how many lines a string wraps to, since
# python-pptx cannot measure rendered text and PowerPoint grows a box beyond its
# declared height at render time -- which is what silently pushed footnotes off
# the bottom of the slide before.
_CALIBRI_CHAR_W = 0.48


def wrapped_height(text, width, size, spacing=1.25):
    """Predicted rendered height of `text` in a box `width` wide, in EMU."""
    chars_per_line = max(1, int((width / Inches(1.0)) * 72.0
                                / (size * _CALIBRI_CHAR_W)))
    lines = 0
    for para in text.split('\n'):
        lines += max(1, -(-len(para) // chars_per_line))
    # 1.2 is the font's own line box; `spacing` is the paragraph multiple on top.
    return Emu(int(lines * size * 1.2 * spacing / 72.0 * Inches(1.0)))


# Footnotes sit on this baseline and grow upward, so a two-line note and a
# one-line note share a bottom edge and never cross the slide edge.
FOOT_BOTTOM = Inches(7.24)


def footnote(slide, text, bottom=FOOT_BOTTOM, size=10.5):
    """One short grey line under the evidence, bottom-aligned and measured.

    Anything that does not fit in two lines belongs in the speaker notes; this
    raises rather than letting the text run off the slide, because a caption
    that overflows is invisible in the editor and obvious on the projector.
    """
    h = wrapped_height(text, CW, size, spacing=1.2)
    if h > Inches(0.62):
        raise ValueError(
            f'footnote wraps to {h / Inches(1.0):.2f}in (max 0.62in); '
            f'move it to speaker notes:\n  {text[:90]}...')
    tb = textbox(slide, X0, bottom - h, CW, h, text, size=size, color=MUTED,
                 spacing=1.2)
    # Stop PowerPoint reflowing the box and re-introducing the overflow.
    tb.text_frame.word_wrap = True
    return tb


def columns(slide, y, cols, width=None, gap=Inches(0.35), size=12.5,
            head_size=13.5):
    """Side-by-side headed text columns for the slides with no report figure."""
    n = len(cols)
    width = width or Emu(int((CW - gap * (n - 1)) / n))
    for i, (head, body) in enumerate(cols):
        x = X0 + Emu(int(i * (width + gap)))
        textbox(slide, x, y, width, Inches(0.4), head, size=head_size,
                bold=True, color=ACCENT)
        textbox(slide, x, y + Inches(0.45), width, Inches(3.2), body,
                size=size, spacing=1.35)


def bullets(slide, y, items, size=13, head_w=Inches(3.0), step=Inches(1.02)):
    """Label-and-body rows, as used by the summary slide of the existing deck."""
    yy = y
    for head, body in items:
        textbox(slide, X0, yy, head_w, Inches(0.9), head, size=size + 0.5,
                bold=True, color=ACCENT)
        textbox(slide, X0 + head_w + Inches(0.18), yy,
                CW - head_w - Inches(0.18), Inches(1.1), body, size=size,
                spacing=1.35)
        yy = yy + step


def picture_slide(prs, kicker, title, conclusion, path, max_h=Inches(4.3),
                  note=None, say=None, gap=Inches(0.24)):
    """The workhorse: claim in the title, report figure carrying it.

    `note` is at most one short line on the slide; `say` is the spoken argument
    and goes to the speaker notes.
    """
    s = add_slide(prs)
    y = header(s, kicker, title, conclusion)
    add_picture(s, path, y + gap, max_h)
    if note:
        footnote(s, note)
    if say:
        notes(s, say)
    return s


def table_slide(prs, kicker, title, conclusion, df, col_w=None,
                highlight_row=None, note=None, say=None, size=11, t_h=None,
                t_w=None):
    """A table slide in house style, centred in the content box."""
    s = add_slide(prs)
    y = header(s, kicker, title, conclusion)
    t_w = t_w or CW
    t_h = t_h or Inches(0.32) * (len(df) + 1)
    x = X0 + Emu(int((CW - t_w) / 2))
    table(s, df, x, y + Inches(0.28), t_w, t_h, col_w=col_w,
          highlight_row=highlight_row, size=size)
    if note:
        footnote(s, note)
    if say:
        notes(s, say)
    return s


# ── Navigation ────────────────────────────────────────────────────────────────
# One entry per section, in order. The outline slide lists these and each
# divider highlights its own, so the section names exist once and the two views
# cannot disagree.
SECTIONS = [
    ('Design and data',
     'What the study adds, what it borrows, and the two constraints that '
     'shape every result after'),
    ('Method',
     'The split, the cross-validation and the metrics the results lean on'),
    ('Milan · same-source validation',
     'The wide margin against CLMS, and the mechanism behind it'),
    ('Vietnam · transfer',
     'Zero-shot fails; local retraining repairs it, but not everywhere'),
    ('Independent validation',
     'Change the reference and most of that margin turns out to be agreement'),
    ('Why transfer fails',
     'Level matching, and the low tail that no level correction could repair'),
    ('Conclusions and limitations',
     'What the study supports, and the five constraints that bound it'),
]


def outline_slide(prs):
    """The map of the deck, listed once after the title."""
    s = add_slide(prs)
    y = header(s, 'Outline', 'Where this goes')
    yy = y + Inches(0.30)
    for i, (name, blurb) in enumerate(SECTIONS, 1):
        textbox(s, X0, yy, Inches(0.6), Inches(0.4), f'{i}', size=15,
                bold=True, color=ACCENT)
        textbox(s, X0 + Inches(0.62), yy, Inches(4.3), Inches(0.4), name,
                size=15, bold=True)
        textbox(s, X0 + Inches(5.05), yy + Inches(0.03), Inches(6.8),
                Inches(0.5), blurb, size=12, color=MUTED, spacing=1.2)
        yy = yy + Inches(0.66)
    return s


def section_slide(prs, index):
    """Divider: the section name, and where it sits in the sequence.

    `index` is 1-based into SECTIONS. Every other section is listed greyed
    above and below, so the divider answers "where are we" and not only
    "what is next".
    """
    name, blurb = SECTIONS[index - 1]
    s = add_slide(prs)
    textbox(s, Inches(0.9), Inches(2.42), CW, Inches(0.35),
            f'SECTION {index} OF {len(SECTIONS)}', size=12, bold=True,
            color=ACCENT)
    textbox(s, Inches(0.9), Inches(2.80), CW, Inches(1.0), name, size=30,
            bold=True)
    rule(s, Inches(3.92), x=Inches(0.9), w=Inches(4.0), color=ACCENT,
         h=Inches(0.035))
    textbox(s, Inches(0.9), Inches(4.16), Inches(9.5), Inches(0.8), blurb,
            size=14, color=MUTED, spacing=1.35)
    # The sequence, with this section marked.
    trail = ' · '.join(
        f'{i}. {n}' for i, (n, _) in enumerate(SECTIONS, 1))
    textbox(s, Inches(0.9), Inches(6.10), CW, Inches(0.9), trail, size=10,
            color=MUTED, spacing=1.25)
    return s


# ══════════════════════════════════════════════════════════════════════════════
# Tables — every value transcribed from report/report.tex
# ══════════════════════════════════════════════════════════════════════════════

# tab:milan-holdout
MILAN_HOLDOUT = pd.DataFrame([
    ['S2 percentile (50 bands)',         '9.462',  '6.389',  '0.927', '−0.104'],
    ['S2 stack (40 bands)',              '10.864', '7.641',  '0.904', '−0.169'],
    ['S2 median (10 bands)',             '11.285', '7.820',  '0.896', '0.046'],
    ['AlphaEarth embeddings (64 bands)', '14.123', '10.675', '0.837', '0.624'],
], columns=['Predictor set', 'RMSE', 'MAE', 'R²', 'Bias'])

# Section 4.1, SVR rows.
MILAN_SVR = pd.DataFrame([
    ['S2 percentile', '9.051'],
    ['S2 stack',      '10.219'],
    ['S2 median',     '10.939'],
    ['AlphaEarth embeddings', '14.756'],
], columns=['Predictor set', 'SVR holdout RMSE'])

# tab:band-importance
BAND_IMPORTANCE = pd.DataFrame([
    ['1', 'B4_p25', '0.1812', '0.3518'],
    ['2', 'B4_p10', '0.0556', '0.1163'],
    ['3', 'B8_p90', '0.0401', '0.0664'],
    ['4', 'B4_p50', '0.0225', '0.0751'],
    ['5', 'B8_p75', '0.0211', '0.0446'],
], columns=['Rank', 'Band', 'Permutation importance', 'Impurity importance'])

# tab:vietnam-holdout
VIETNAM_HOLDOUT = pd.DataFrame([
    ['Hanoi', 'AlphaEarth', 'zero-shot',     '35.960', '30.140', '−0.070', '−24.930'],
    ['Hanoi', 'AlphaEarth', 'local retrain', '23.860', '17.720', '0.529',  '−0.690'],
    ['Hanoi', 'S2 median',  'zero-shot',     '37.150', '28.930', '−0.142', '−23.790'],
    ['Hanoi', 'S2 median',  'local retrain', '24.050', '18.490', '0.522',  '−2.080'],
    ['HCMC',  'AlphaEarth', 'zero-shot',     '40.650', '34.170', '−0.279', '−29.760'],
    ['HCMC',  'AlphaEarth', 'local retrain', '21.310', '16.580', '0.649',  '0.400'],
    ['HCMC',  'S2 median',  'zero-shot',     '35.190', '26.980', '0.042',  '−23.180'],
    ['HCMC',  'S2 median',  'local retrain', '22.880', '17.930', '0.595',  '−1.900'],
], columns=['City', 'Predictors', 'Scenario', 'RMSE', 'MAE', 'R²', 'Bias'])

# tab:independent-all
INDEPENDENT_ALL = pd.DataFrame([
    ['Milan', 'S2 stack',            'model',     '24.644', '21.559', '16.551', '0.652', '−3.344'],
    ['Milan', 'S2 percentile',       'model',     '24.809', '21.874', '16.486', '0.647', '−3.342'],
    ['Milan', 'emb_RF',              'model',     '25.625', '22.420', '18.299', '0.624', '−1.622'],
    ['Milan', 'S2 median',           'model',     '25.984', '22.917', '18.363', '0.613', '−4.176'],
    ['Milan', 'CLMS',                'reference', '26.253', '24.411', '14.606', '0.605', '2.263'],
    ['Hanoi', 'emb_localrf',         'model',     '26.502', '23.266', '19.588', '0.649', '6.592'],
    ['Hanoi', 'S2_median_localrf',   'model',     '27.282', '23.885', '21.320', '0.628', '8.181'],
    ['Hanoi', 'S2_median_zeroshot',  'model',     '33.791', '31.195', '24.469', '0.429', '−15.876'],
    ['Hanoi', 'emb_zeroshot',        'model',     '34.352', '31.061', '29.537', '0.410', '−15.716'],
    ['Hanoi', 'GHSL',                'reference', '40.345', '38.833', '27.052', '0.187', '19.680'],
    ['HCMC',  'S2_median_zeroshot',  'model',     '25.950', '23.420', '16.779', '0.665', '−6.827'],
    ['HCMC',  'emb_localrf',         'model',     '27.242', '24.011', '20.294', '0.630', '11.088'],
    ['HCMC',  'S2_median_localrf',   'model',     '29.615', '26.484', '23.030', '0.563', '12.233'],
    ['HCMC',  'GHSL',                'reference', '37.355', '35.597', '25.730', '0.305', '19.800'],
    ['HCMC',  'emb_zeroshot',        'model',     '38.494', '35.775', '32.404', '0.262', '−19.641'],
], columns=['City', 'Map', 'Role', 'RMSE', 'RMSE_corr', 'MAE', 'R²', 'Bias'])

# The training-product rows of tab:independent-all, for slide 14's alternative
# reading. Kept as a subset of the same frame so the numbers cannot diverge.
TRAINING_PRODUCTS = INDEPENDENT_ALL[
    INDEPENDENT_ALL['Role'] == 'reference'
][['City', 'Map', 'RMSE', 'MAE', 'R²', 'Bias']].reset_index(drop=True)

# HCMC rows of tab:independent-all, for the level-matching segment.
HCMC_ROWS = INDEPENDENT_ALL[INDEPENDENT_ALL['City'] == 'HCMC'][
    ['Map', 'RMSE', 'MAE', 'R²', 'Bias']
].reset_index(drop=True)

# tab:paired-wilcoxon
PAIRED = pd.DataFrame([
    ['S2 median', 'S2 percentile', '18.36', '16.49', '0.92',  '5.95e-09', '3.57e-08', 'yes'],
    ['S2 median', 'S2 stack',      '18.36', '16.55', '1.07',  '4.33e-05', '1.30e-04', 'yes'],
    ['emb_RF',    'S2 stack',      '18.30', '16.55', '0.60',  '9.62e-04', '1.92e-03', 'yes'],
    ['emb_RF',    'S2 percentile', '18.30', '16.49', '0.31',  '4.56e-03', '6.84e-03', 'yes'],
    ['S2 stack',  'S2 percentile', '16.55', '16.49', '0.19',  '6.55e-01', '7.86e-01', 'no'],
    ['emb_RF',    'S2 median',     '18.30', '18.36', '−0.64', '7.90e-01', '7.90e-01', 'no'],
], columns=['Map A', 'Map B', 'MAE A', 'MAE B', 'Median diff.', 'p', 'q (BH)',
            'Distinguishable'])

# tab:milan-error-dist
ERROR_DIST = pd.DataFrame([
    ['S2 stack',      '16.55', '24.64', '10.38', '39.37', '96.26',  '32.7', '6.7'],
    ['S2 percentile', '16.49', '24.81', '9.09',  '40.76', '94.92',  '34.2', '6.7'],
    ['emb_RF',        '18.30', '25.63', '14.38', '43.67', '82.84',  '29.8', '7.3'],
    ['S2 median',     '18.36', '25.98', '12.17', '41.49', '94.41',  '21.8', '6.9'],
    ['CLMS',          '14.61', '26.25', '3.00',  '45.20', '100.00', '53.3', '8.7'],
], columns=['Map', 'MAE', 'RMSE', 'Median error', 'p90', 'Max',
            'Within 5 pp (%)', 'Over 50 pp (%)'])

# Section 7.2 mean levels, against the interpreted reference means.
#
# The report gives the two zero-shot means per city individually but reports the
# four local-retrain means only as a range, "between 37.87 and 39.97 across the
# two cities", without assigning either endpoint to a city and map. So the
# retrain rows carry the range rather than a per-row value: inventing the
# split would put a number on a slide that the report does not contain. The
# bias column is the independent-validation bias from tab:independent-all,
# quoted at the report's own three decimals.
LEVELS = pd.DataFrame([
    ['Hanoi', 'emb_zeroshot',       'zero-shot',     '61.77',         '46.05', '−15.716'],
    ['Hanoi', 'S2_median_zeroshot', 'zero-shot',     '61.93',         '46.05', '−15.876'],
    ['Hanoi', 'emb_localrf',        'local retrain', '37.87 … 39.97', '46.05', '6.592'],
    ['Hanoi', 'S2_median_localrf',  'local retrain', '37.87 … 39.97', '46.05', '8.181'],
    ['HCMC',  'emb_zeroshot',       'zero-shot',     '70.70',         '51.06', '−19.641'],
    ['HCMC',  'S2_median_zeroshot', 'zero-shot',     '57.89',         '51.06', '−6.827'],
    ['HCMC',  'emb_localrf',        'local retrain', '37.87 … 39.97', '51.06', '11.088'],
    ['HCMC',  'S2_median_localrf',  'local retrain', '37.87 … 39.97', '51.06', '12.233'],
], columns=['City', 'Map', 'Scenario', 'Mean predicted', 'Reference mean',
            'Bias'])

# tab:tail-spread
TAIL_SPREAD = pd.DataFrame([
    ['Hanoi', 'emb_zeroshot',       'zero-shot',     '3.1',   '37'],
    ['Hanoi', 'S2_median_zeroshot', 'zero-shot',     '30.6',  '53'],
    ['Hanoi', 'emb_localrf',        'local retrain', '136.0', '61'],
    ['Hanoi', 'S2_median_localrf',  'local retrain', '124.4', '51'],
    ['HCMC',  'emb_zeroshot',       'zero-shot',     '0.0',   '26'],
    ['HCMC',  'S2_median_zeroshot', 'zero-shot',     '68.7',  '75'],
    ['HCMC',  'emb_localrf',        'local retrain', '108.3', '57'],
    ['HCMC',  'S2_median_localrf',  'local retrain', '104.0', '51'],
], columns=['City', 'Map', 'Scenario', 'Tail retained (%)',
            'Spread retained (%)'])

# tab:bias-recovery
BIAS_RECOVERY = pd.DataFrame([
    ['Hanoi', 'GHSL', '19.68', 'emb_localrf',       '6.59',  '13.09', '66.5'],
    ['Hanoi', 'GHSL', '19.68', 'S2_median_localrf', '8.18',  '11.50', '58.4'],
    ['HCMC',  'GHSL', '19.80', 'emb_localrf',       '11.09', '8.71',  '44.0'],
    ['HCMC',  'GHSL', '19.80', 'S2_median_localrf', '12.23', '7.57',  '38.2'],
], columns=['City', 'Target', 'Target bias', 'Map', 'Map bias',
            'Recovered (pp)', 'Recovered (%)'])

# tab:rule-sensitivity
RULE_SENSITIVITY = pd.DataFrame([
    ['S2 stack',      '24.64', '24.54', '20.98', '1', '1', '1'],
    ['S2 percentile', '24.81', '24.71', '21.37', '2', '2', '2'],
    ['emb_RF',        '25.63', '25.54', '23.03', '3', '3', '4'],
    ['S2 median',     '25.98', '25.94', '22.98', '4', '4', '3'],
    ['CLMS',          '26.25', '25.97', '24.08', '5', '5', '5'],
], columns=['Map', 'Strict', 'B', 'C', 'Rank strict', 'Rank B', 'Rank C'])

# Section 5.2 per-class MAE, the classes where the ordering reverses.
PERCLASS_C6 = pd.DataFrame([
    ['Hanoi', 'AlphaEarth', 'C0 (0 %)',    '40.75', '6.36',  'retrain better'],
    ['Hanoi', 'AlphaEarth', 'C1 (1–20 %)', '50.08', '20.12', 'retrain better'],
    ['HCMC',  'AlphaEarth', 'C0 (0 %)',    '49.05', '5.15',  'retrain better'],
    ['Hanoi', 'AlphaEarth', 'C6 (100 %)',  '17.25', '30.95', 'retrain worse'],
    ['HCMC',  'AlphaEarth', 'C6 (100 %)',  '12.93', '25.20', 'retrain worse'],
    ['Hanoi', 'S2 median',  'C6 (100 %)',  '8.07',  '26.16', 'retrain worse'],
    ['HCMC',  'S2 median',  'C6 (100 %)',  '5.91',  '22.58', 'retrain worse'],
], columns=['City', 'Predictors', 'Class', 'Zero-shot MAE', 'Retrain MAE',
            'Direction'])


# ══════════════════════════════════════════════════════════════════════════════
# Deck
# ══════════════════════════════════════════════════════════════════════════════


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # ── 1 Title ──────────────────────────────────────────────────────────────
    s = add_slide(prs)
    textbox(s, Inches(0.9), Inches(2.15), Inches(11.5), Inches(0.35),
            'INTERNAL REVIEW  ·  IMD MAPPING', size=12, bold=True, color=ACCENT)
    textbox(s, Inches(0.9), Inches(2.55), Inches(11.5), Inches(1.6),
            'Impervious surface density from Sentinel-2\n'
            'composites and AlphaEarth embeddings',
            size=32, bold=True, spacing=1.15)
    rule(s, Inches(4.35), x=Inches(0.9), w=Inches(4.0), color=ACCENT,
         h=Inches(0.035))
    textbox(s, Inches(0.9), Inches(4.6), Inches(11.5), Inches(1.0),
            'Milan · Hanoi · Ho Chi Minh City · 2018 · 10 m\n'
            'Companion to the AlphaEarth study by Matej Žgela',
            size=14.5, color=MUTED, spacing=1.4)
    textbox(s, Inches(0.9), Inches(6.25), Inches(11.5), Inches(0.5),
            'Xiao Tan  ·  Politecnico di Milano', size=12, color=MUTED)
    notes(s, """
The through-line for the whole session: most of the same-source advantage was
agreement with CLMS rather than accuracy. Same-source validation is the right
instrument for model selection and the wrong one for claiming accuracy.

This extends Žgela's AlphaEarth study, which is assumed read. Three changes:
Sentinel-2 composites as an alternative predictor set, two Vietnamese cities so
transfer can be tested, and a second validation against plots no model saw.
""")

    # ── 2 Outline ────────────────────────────────────────────────────────────
    outline_slide(prs)

    # ═══════════════ SECTION 1 · Design and data ═════════════════════════════
    section_slide(prs, 1)

    # ── Three additions, on a verified baseline ──────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Scope',
               'Three additions to an established study, on a baseline verified '
               'to reproduce',
               'The AlphaEarth method and the shared Milan sample set are '
               "Žgela's and are used as supplied.")
    columns(s, y + Inches(0.32), [
        ('Added by this project',
         'Explicit Sentinel-2 composites as an alternative predictor set.\n\n'
         'Two Vietnamese cities, turning a single-city study into a test of '
         'whether a model transfers.\n\n'
         'A second validation against photo-interpreted plots no model saw.'),
        ('Taken from Žgela',
         'The 3 500-point stratified sample, the 1 km spatial blocking and the '
         '250 m buffer.\n\n'
         'The treatment of the 64-dimensional embedding, used whole.\n\n'
         'Three results reproduced here are labelled as his where they '
         'appear.'),
        ('Verified, not claimed',
         'The embeddings pipeline was independently re-run and reproduces his '
         'published holdout figures exactly.\n\n'
         'RF 14.123 / 10.675 / 0.837 / +0.624 against his 14.12 / 10.68 / '
         '0.837 / +0.62.'),
    ])
    footnote(s, 'The reproduction is a check that the shared baseline has not '
                'drifted, not a new result.')
    notes(s, """
Why the reproduction is reported at all: every comparison in the Milan and
discussion sections measures a new predictor set against that baseline, so a
baseline that had drifted would move those comparisons without announcing
itself. Both estimators reproduce: SVR gives 14.756 / 11.400 / 0.822 / +0.274
against his 14.76 / 11.40 / 0.822 / +0.27.

On using the embeddings whole: Žgela tested every band against the IMD groups
by Kruskal-Wallis and found 60 of 64 differ significantly across classes, and a
separate feature-selection experiment found the full set to outperform any
reduced subset. So the obvious question — would a smaller subset do as well —
has already been answered in the negative on this same data.

The three reproduced results are the CV-versus-holdout reversal, the per-class
pattern of local retraining, and the qualitative observation behind the bias
recovery.
""")

    # ── Every map is scored twice ────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Method · the hinge',
               'Every map is scored twice, against two references that are '
               'never merged',
               'This distinction is the methodological hinge of the study, and '
               'everything that follows depends on keeping the two apart.')
    columns(s, y + Inches(0.32), [
        ('Same-source validation',
         'Scores each map against the product it was trained on: CLMS in '
         'Milan, GHS-BUILT-S in Hanoi and HCMC.\n\n'
         'Runs on the spatial holdout — 1 014 points in Milan, 895 in Hanoi, '
         '887 in HCMC.\n\n'
         'Measures agreement with the training target. It cannot distinguish '
         'a good map from one that merely resembles its labels.'),
        ('Independent validation',
         'Scores every map against 450 photo-interpreted plots per city, '
         '1 350 in total, on 2018 imagery.\n\n'
         'No model saw them at any stage.\n\n'
         'Measures accuracy against an independent reference, at the cost of '
         'a smaller and stratified sample.'),
    ], width=Inches(5.6))
    footnote(s, 'Bias is observed minus predicted: positive means the map '
                'under-predicts. Identical in both validations.')
    notes(s, """
Both are necessary and neither substitutes for the other. Same-source is
available for every candidate model, uses the full spatial holdout, and is the
natural instrument for choosing among models. What it cannot do is separate a
good map from one that has learned to resemble its labels: a model scored
against the product it was fitted to is rewarded for reproducing that product,
including wherever the product is wrong.

That is not hypothetical here — the independent validation finds both training
products score no better than the models fitted to them.

The two are never merged and their numbers are never compared directly. They
are scored against different references, on different samples, at different
sizes, so a difference between a same-source number and an independent one
would measure the change of reference rather than anything about a map. The one
place they are set side by side is the compression slide, which has that
relationship as its subject.

On the sign convention: the two validations produce biases of opposite sign and
both are correct. In Vietnam the models read higher than GHS-BUILT-S, giving
negative biases; against photo-interpretation GHS-BUILT-S reads lower than the
reference, giving positive ones. Different comparisons — do not read the signs
across them.
""")

    # ── The two targets ──────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Data · targets',
               'The two training targets do not measure the same quantity',
               'Both are 10 m and both report a percentage per pixel, so they '
               'enter the modelling identically. What they measure differs, '
               'and the difference is not noise.')
    columns(s, y + Inches(0.32), [
        ('CLMS — Milan',
         'Imperviousness density for 2018. Measures sealed surface: the '
         'fraction of a pixel water cannot pass through.\n\n'
         'Includes roads, pavements, car parks and rooftops alike.'),
        ('GHS-BUILT-S — Hanoi, HCMC',
         'Built-up surface for 2018. A narrower quantity: buildings and a '
         'limited set of other roofed infrastructure.\n\n'
         'Does not include roads. Žgela calls this an inherent limitation of '
         'the chosen reference.'),
        ('Why it was still the right choice',
         'No other suitable 2018 reference product existed for the two '
         'Vietnamese cities.\n\n'
         'Matching the label year to the imagery year was the binding '
         'constraint.'),
    ])
    footnote(s, 'This returns later as a number: GHS-BUILT-S under-marks the '
                'interpreted reference by close to 20 pp in both cities.')
    notes(s, """
Flag this early. A definitional mismatch met without this slide reads as a
measurement error, and the +19.68 / +19.80 pp result later is exactly that
mismatch appearing as a number.

Žgela states the road exclusion twice in his report and it is taken from him
rather than asserted here: the product accounts only for built-up surfaces,
namely buildings and a limited set of other roofed infrastructure.

On the choice being deliberate rather than by default: a target with a known
definitional gap was preferred to a target from the wrong year, or to no
Vietnamese experiment at all.
""")

    # ── The photo-interpreted reference (merged: plots + metrics) ────────────
    s = add_slide(prs)
    y = header(s, 'Data · the independent reference',
               'How the reference was built, and what may be claimed from it',
               '450 plots per city, 1 350 in total, produced by Keerthana '
               'Kirubakaran in Google Earth Pro on 2018 imagery.')
    columns(s, y + Inches(0.32), [
        ('Plot geometry',
         'A plot is a 10 m unit area — exactly one Sentinel-2 pixel and one '
         'pixel of every map under test.\n\n'
         'Each is subdivided into nine sub-cells, each interpreted '
         'individually. Plot IMD is the percentage of sub-cells that are '
         'impervious.\n\n'
         'Sub-cells are collapsed to one value per plot before anything is '
         'scored, so every metric runs on 450 observations per city.'),
        ('The three coding rules',
         'strict — the primary rule: parking, pavement, road, roof, railroad, '
         'airport, pool.\n\n'
         'B — adds permeable pavement, matching the sealed-surface definition '
         'CLMS works to.\n\n'
         'C — adds unpaved dirt road and heavily compacted bare soil.\n\n'
         'Paved roads are impervious under all three, so no choice of rule '
         'removes the GHS-BUILT-S mismatch.'),
        ('The metrics',
         'RMSE and MAE in IMD percentage points. MAE weights every plot by how '
         'wrong it is; RMSE squares first and is driven by the largest errors, '
         'so the two can disagree about which map is better.\n\n'
         'RMSE_corr removes a binomial estimate of the reference\'s own noise. '
         'It is an upper bound on map error, never a point estimate.'),
    ])
    notes(s, """
On RMSE_corr, which is the one metric that invites misuse. A plot's IMD is a
proportion estimated from nine sub-cells, so the reference carries sampling
error of its own. The correction subtracts a binomial estimate of that error
and is floored at zero.

The independence assumption behind it does not hold: nine sub-cells within a
single 10 m pixel share land cover and are spatially correlated, so the binomial
calculation understates the true reference noise and the correction removes less
error than it should. The true map error is therefore at or below RMSE_corr. The
correct use is to say a map's error is at most some value, never that it equals
it. Saying the four Milan maps lie between 21.559 and 22.917 corrected is a
statement about bounds; claiming any of them achieves 21.559 is not supported.

R-squared: the proportion of reference variance the map accounts for. At or
below zero it is no more informative than predicting the mean everywhere — which
is what three of the four zero-shot combinations do.

One code, Rock/material, is ambiguous between sealed and unsealed and is dropped
wherever it occurs, with the denominator renormalised so a plot with one dropped
sub-cell scores out of eight. It occurs once, in Milan.

The rare codes bound how much the rule choice can matter: in Milan permeable
pavement occurs in 23 sub-cells across 6 plots, dirt road in 112 across 18. In
both Vietnamese cities permeable pavement does not occur at all, so rule B is
identical to strict there by construction.
""")

    # ── Composite depth ──────────────────────────────────────────────────────
    picture_slide(
        prs, 'Data · Sentinel-2',
        'Milan retains 30 usable dates; Hanoi retains 4 and HCMC 3',
        'Both Vietnamese cities are screened one rung looser than Milan and '
        'still yield almost nothing.',
        fig('fig_composite_depth.png'), max_h=Inches(4.0),
        note='Only the median composite is computable in Vietnam — an archive '
             'limit, not a modelling preference.',
        say="""
Screening is per acquisition date on three criteria over the city's area of
interest: cloud cover, share of valid pixels, and at least 95 % scene coverage.
Milan passes at the strict setting, cloud below 20 % and valid above 90 %.
Neither Vietnamese city yields a workable set there, so both are screened one
rung looser at cloud below 35 % and valid above 80 %.

Three composite methods are defined: median (10 bands), stack (four dates one
per season, 40 bands), percentile (p10/p25/p50/p75/p90, 50 bands).

Why only median survives in Vietnam. A percentile needs enough observations on
either side of it; the guard scales with the number requested, so five
percentiles require at least 17 dates. This was tested rather than assumed: the
scene search evaluates a ceiling case with every threshold disabled and every
candidate accepted regardless of cloud. Even then HCMC reaches 16 against the 17
required — it fails by one. Hanoi reaches 10 and fails by seven.

The narrowness of HCMC's margin does not weaken the conclusion. The ceiling set
is not a usable alternative that was passed over: it includes every acquisition
rejected for cloud, which is how 16 becomes a screened count of 3. A percentile
composite computed from it would be a percentile of largely cloudy observations.

Stack fails for the same reason at a smaller count: it needs four dates one per
season and HCMC's three fall in two months.

Two properties that matter later. Milan's composite is near-annual rather than
annual — January, February and May are absent from all 30 dates. And HCMC's is
thinner than a count of three suggests: its dates are 12 February, 24 December
and 29 December, and the two December acquisitions are five days apart, so it is
effectively one February look plus one late-December look.

Do not read median's use in Vietnam as a finding that median is the better
choice — it is the weakest of the three in Milan, where all three could be
computed.
""")

    # ═══════════════ SECTION 2 · Method ══════════════════════════════════════
    section_slide(prs, 2)

    # ── Spatial split ────────────────────────────────────────────────────────
    picture_slide(
        prs, 'Method · sampling',
        'Train and test are separated spatially, not at random',
        'Milan: 1 km blocks assigned whole to training or testing, plus a '
        '250 m buffer removing test points near any training point.',
        fig('outputs_v2', 'fig01_spatial_split.png'), max_h=Inches(4.0),
        note='2 449 training and 1 014 test points, roughly 70/30. The design '
             'is Žgela\'s and is used unchanged.',
        say="""
The CLMS reference was classified into seven IMD groups and 500 points drawn at
random within each, giving 3 500. Stratifying this way rather than sampling
uniformly is what puts enough points in the sparse middle of the range, which an
unstratified draw over a city would leave nearly empty.

Why spatial rather than random splitting: random splitting would place training
and test points metres apart in the same neighbourhood, where they share land
cover and often the same rooftops, and would return an accuracy figure measuring
interpolation between neighbouring pixels rather than prediction.

Two consequences for this deck. First, the 1 014-point holdout is the same
holdout throughout the Milan section — notebook 01b imports the split from the
embeddings run rather than recomputing it, so all four predictor sets are scored
on exactly the same held-out points. That is what makes it a comparison of
predictors. Second, the 1 014 figure matches Žgela's, which is one of the checks
that the shared baseline was correctly reconstructed.

Žgela checked the design's own spatial randomness with an average nearest
neighbour index, running from 1.02 for the 0 % class down to 0.75 for the 100 %
class. The lower value records that fully impervious pixels cluster in the city
centre; he acknowledges it as a sampling limitation rather than correcting for
it, and it is repeated here on the same terms.

Vietnam is sampled and split on the same design against GHS-BUILT-S, giving 895
test points in Hanoi and 887 in HCMC.
""")

    # ── CV inflation ─────────────────────────────────────────────────────────
    picture_slide(
        prs, 'Method · cross-validation',
        'Spatial and random cross-validation agree to within about one per cent',
        'CV RMSE under spatial blocking against random folds, Milan training '
        'set, by estimator and block size. Bold marks the block each estimator '
        'was tuned at.',
        fig('fig_cv_inflation.png'), max_h=Inches(4.0),
        note='The largest absolute inflation is 0.3 %. This does not say '
             'spatial blocking was unnecessary.',
        say="""
The agreement says the buffering and blocking have already removed what leakage
there was to remove, and that the tuning scores are not inflated by proximity
between folds. It does not say the blocking was pointless: the reason the two
agree is that the split was built to make them agree.

Cross-validation is spatial throughout, using the same block structure as the
train/test split, so a fold boundary is a spatial boundary.

Important: CV scores are used for tuning and are never quoted as holdout
performance. They score scikit-learn models on training-set folds, whereas every
accuracy figure in this deck is scored on data held out from training.

Estimator scope, fixed once. Three estimators were tuned; two are carried
forward, random forest and SVR. SVR is evaluated in Milan only. Every model
outside the Milan section is a random forest, for two reasons: the transfer
experiment requires a random forest by construction, and the comparison across
predictor sets, scenarios and cities is only a comparison of those things if the
estimator is held fixed. Only estimators whose trained form can be applied to a
raster through the Earth Engine Python API were considered, since every map is
produced by predicting over the full scene rather than scoring a table of
points.
""")

    # ═══════════════ SECTION 3 · Milan, same-source ══════════════════════════
    section_slide(prs, 3)

    # ── Milan ranking (merged with the SVR table) ────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Milan · same-source',
               'Against CLMS, all three Sentinel-2 composites beat the '
               'embeddings, and the margin is wide',
               'Percentile reaches RMSE 9.462 against the embeddings\' 14.123, '
               'a reduction of 33 %. The ordering is the same on RMSE, MAE and '
               'R², so it is not an artefact of one metric.')
    add_picture(s, fig('fig_milan_predictor_ranking.png'), y + Inches(0.22),
                Inches(2.62))
    table(s, MILAN_HOLDOUT, X0 + Inches(1.6), Inches(5.20), Inches(8.7),
          Inches(1.5), highlight_row=0, size=10.5)
    footnote(s, 'GEE random forest, 1 014-point spatial holdout. The SVR rows '
                'run in the same order: 9.051 / 10.219 / 10.939 / 14.756.')
    notes(s, """
These are agreement with CLMS, not accuracy. Say so here — the independent
validation later compresses this spread about 6.4-fold.

The ordering holds on RMSE, MAE and R-squared, so it is not an artefact of a
single metric, and the bars in all three panels start at zero so bar length is
proportional and the spread is not exaggerated by a truncated axis.

The gap between the best composite and the embeddings, 4.661 RMSE, is larger
than the gap between the best and worst composite, 1.823.

All four maps are close to unbiased on this validation, between −0.169 and
+0.624, which is exactly what you expect of a model fitted to the product it is
then scored against.

Because the SVR ordering is identical, the advantage does not depend on the
estimator. SVR appears in Milan only, for the reasons on the cross-validation
slide.

If asked about the CV-versus-holdout reversal: SVR wins cross-validation and
loses the holdout, reproducing Žgela's result. On the embeddings run SVR tunes
to CV RMSE 11.711 at its selected 500 m block against RF's 13.162 at 1 000 m,
then loses all three holdout metrics. The reversal carries a confound — holdout
rows are scored on Earth Engine rasters while CV numbers come from tuned
scikit-learn models, and the parameter translation is lossy in both directions,
so overfitting to the folds and estimator translation cannot be separated from
these runs. RF is carried forward because the transfer design requires it, not
because SVR could not be rastered: the Milan SVR raster was produced and
retained.
""")

    # ── Holdout scatter ──────────────────────────────────────────────────────
    picture_slide(
        prs, 'Milan · same-source',
        'Observed against predicted on the holdout, both estimators',
        'S2 percentile composite, 1 014-point spatial holdout, scored against '
        'CLMS.',
        fig('outputs_S2_percentile_p10p25p50p75p90',
            'fig07_holdout_scatter.png'), max_h=Inches(4.2),
        say="""
This is the plot-level view behind the ranking table. Both estimator panels
carry their own RMSE, MAE, R-squared and bias.

Useful for the reversal question: the SVR panel is the map that won
cross-validation and lost here.
""")

    # ── Per-class Milan ──────────────────────────────────────────────────────
    picture_slide(
        prs, 'Milan · same-source',
        'RMSE, MAE and bias per IMD class, percentile composite',
        'GEE random forest, scored against CLMS on the 1 014-point holdout.',
        fig('outputs_S2_percentile_p10p25p50p75p90',
            'figC_perclass_GEE_RF.png'), max_h=Inches(4.3),
        say="""
Breaking the holdout down by class, for anyone who wants to know where the
Milan error sits rather than only its total.

Note the contrast with Vietnam later: here there is no zero-shot/retrain
comparison to make, because the Milan model is trained on Milan.
""")

    # ── Milan raster ─────────────────────────────────────────────────────────
    picture_slide(
        prs, 'Milan · same-source',
        'The disagreement with CLMS is structured and two-sided',
        'Observed CLMS, the predicted map and their difference, percentile '
        'composite. Positive difference means the model reads more impervious '
        'than CLMS.',
        fig('fig_milan_raster_comparison.png'), max_h=Inches(4.05),
        note='Qualitative support only: this whole-scene view is not the '
             '1 014-point holdout, and no number is quoted from it.',
        say="""
The two upper panels agree on the structure of the conurbation: the dense core,
the satellite towns to the north, the largely agricultural south.

The difference panel is where the disagreement is legible. It is close to zero
over most of the rural area and over the interior of the built-up core, and
departs from CLMS in two places.

First, a fine network of positive lines threading the countryside, following the
road and canal network: the model reads these narrow sealed features as more
impervious than CLMS does. Second, a mild negative cast over the densest part of
the city centre, where the model sits below CLMS. The predicted panel also
carries small unmapped gaps along the watercourses that CLMS fills.

Be careful with the road reading here. CLMS measures sealed surface and includes
roads by design, so this is not the road-exclusion story that applies to
GHS-BUILT-S in Vietnam. What this shows is a disagreement about how narrow
sealed features are resolved, in both directions, not a definitional gap.
""")

    # ── Where the signal is ──────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Milan · mechanism',
               'The advantage is interpretable: it comes from the quantiles a '
               'median discards',
               'Four of the top five bands are low percentiles of red or high '
               'percentiles of near infrared. B4_p25 alone carries more than '
               'three times the permutation importance of the next band.')
    add_picture(s, fig('outputs_S2_percentile_p10p25p50p75p90',
                       'figD_importance_RF.png'),
                y + Inches(0.22), Inches(2.55))
    table(s, BAND_IMPORTANCE, X0 + Inches(2.4), Inches(5.12), Inches(7.1),
          Inches(1.8), highlight_row=0, size=10.5)
    footnote(s, 'Permutation importance on the holdout, with mean decrease in '
                'impurity alongside.')
    notes(s, """
The point: the percentile composite does not simply carry more bands than the
median — it carries the particular bands the median throws away. That is a
mechanistic explanation of the ranking, not just an empirical one.

On the embeddings comparison, and be precise here. Žgela reports band importance
for the embeddings in his study; his two most important predictors are bands B16
and B08 of the 64-dimensional embedding, which have no direct physical
interpretation. What this project did not do is run the equivalent comparison
between the two feature spaces, so no claim is made here about how the two
explanations compare. The honest statement is that the Sentinel-2 side gives an
interpretable account of why it works, and that this project did not test
whether the embeddings admit one.
""")

    # ═══════════════ SECTION 4 · Vietnam transfer ════════════════════════════
    section_slide(prs, 4)

    # ── Transfer fails, embeddings ───────────────────────────────────────────
    picture_slide(
        prs, 'Vietnam · same-source',
        'Zero-shot transfer of a Milan-trained model fails in both cities',
        'AlphaEarth embeddings. R² is at or below zero in three of the four '
        'city and predictor combinations, which is no more informative than '
        'predicting the mean everywhere.',
        fig('outputs_transfer_v2', 'fig01_transfer_comparison.png'),
        max_h=Inches(4.05),
        note='Every bar is scored against the training target, so a bias bar '
             'near zero means agreement with GHSL, not a correct map.',
        say="""
Local retraining recovers R-squared to between 0.522 and 0.649 in every case,
and cuts RMSE by roughly a third to a half: 35.960 to 23.860 and 37.150 to
24.050 in Hanoi, 40.650 to 21.310 and 35.190 to 22.880 in HCMC.

The bias column identifies the failure mode. Every zero-shot bias is large and
negative, between −23.180 and −29.760, so the transferred models read
systematically more impervious than GHSL across the whole test set. They are not
scattered around the reference; they sit above it. Local retrains bring bias to
between −2.080 and +0.400.

The fourth combination, S2 median in HCMC at R-squared 0.042, is not a
counter-example so much as a weaker instance of the same failure.

The raster view of this same failure — GHSL, the Milan transfer and the local
retrain side by side for both cities — is available if the level shift needs
showing directly rather than as a metric.
""")

    # ── Transfer fails, S2 median ────────────────────────────────────────────
    picture_slide(
        prs, 'Vietnam · same-source',
        'The Sentinel-2 features fail the same way, so it is not a property '
        'of the embeddings',
        'S2 median composite: the same four metrics and the same two '
        'scenarios. Read the two slides as a pair — the shape of the result is '
        'the same in both.',
        fig('outputs_transfer_S2_median', 'fig01_transfer_comparison.png'),
        max_h=Inches(4.05),
        note='Caveat: composite depth is confounded with predictor type here, '
             'so the ordering between the two arms is not controlled.',
        say="""
Both predictor sets fail in the same way and to a similar degree, which is what
makes this a statement about transfer rather than about a particular feature
space.

The caveat in full. The two zero-shot experiments are not equally handicapped:
the embeddings compare annual coverage against annual coverage, while the S2
median compares Milan's 30-date composite against 3 to 4 Vietnamese dates. So
the near-equality of the two failures should not be read as a controlled
comparison between them, and nothing supports a statement that one predictor set
transfers better than the other. The shared conclusion — both fail, local
retraining repairs both — does not rest on that ordering and is unaffected.

The figure code is identical in the two notebooks; only the raster suffix and
one suptitle differ, which is why each figure names its own predictor set and
reference.
""")

    # ── Vietnam holdout table ────────────────────────────────────────────────
    table_slide(
        prs, 'Vietnam · same-source',
        'Both scenarios, both predictor sets, both cities',
        'Scored against GHS-BUILT-S on each city\'s spatial holdout: 895 '
        'points in Hanoi, 887 in HCMC. Bias is observed minus predicted, so a '
        'negative value means the map over-predicts.',
        VIETNAM_HOLDOUT, size=11,
        note='Zero-shot R² is at or below zero in three of four combinations; '
             'every local retrain lands between 0.522 and 0.649.',
        say="""
The numbers behind the two previous figures, if anyone wants to read a specific
cell.

The pattern to point at: every zero-shot bias is large and negative, between
−23.180 and −29.760, and every local retrain sits between −2.080 and +0.400.
That is the level mismatch the discussion section takes up as mechanism one.
""")

    # ── Per-class Vietnam ────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Vietnam · same-source',
               'Retraining is not uniformly better: above 80 % imperviousness '
               'it is worse',
               'Large gains in the low and middle classes, a clear reversal in '
               'the top class, in both cities and for both predictor sets.')
    add_picture(s, fig('outputs_transfer_v2', 'fig02_per_class_mae.png'),
                y + Inches(0.22), Inches(2.28))
    table(s, PERCLASS_C6, X0 + Inches(1.9), Inches(4.78), Inches(8.1),
          Inches(1.82), size=9.5)
    footnote(s, 'MAE per IMD class, AlphaEarth embeddings, scored against '
                'GHS-BUILT-S. Žgela reports the same pattern.')
    notes(s, """
This is a real limitation of local retraining, not noise, and it is reported
rather than set aside.

The mechanism is visible in the same rows. The transferred models over-predict
everywhere, which is ruinous in the low classes — a map that cannot predict low
values is worst where the reference is lowest — and incidentally close to right
in the highest class, where the reference is near 100 % and a map biased upward
has little room to err. Retraining removes the upward bias globally, which fixes
the low classes and removes the accident that was flattering the top one.

Žgela reports the same pattern: improvements mainly in classes C0 to C3, with
the retrained model challenged at the top of the range.

If asked why there is no per-class R-squared: restricting to a single IMD class
removes most of the variance R-squared is normalised by, so every defined
per-class value is negative even where the same model reaches a global 0.522 to
0.649. That is arithmetic, not model failure. C0 and C6 are single-valued
strata, so their variance is exactly zero and R-squared is undefined. Per-class
RMSE, MAE and bias are the appropriate within-class measures.
""")

    # ═══════════════ SECTION 5 · Independent validation ══════════════════════
    section_slide(prs, 5)

    # ── The compression (merged with the fifteen-map table) ──────────────────
    s = add_slide(prs)
    y = header(s, 'Independent validation · the result',
               'Change the reference and the Milan spread compresses about '
               '6.4-fold',
               'The four-way spread falls from 4.661 RMSE — 33.0 % of the '
               'worst map — to 1.340, or 5.2 %. Most of what the first '
               'validation measured as separation was agreement with CLMS '
               'rather than accuracy.')
    # Two columns: the figure carries the compression, the table the fifteen
    # maps it summarises. max_w is the figure's own column, so add_picture
    # centres it within that column rather than across the whole content box.
    add_picture(s, fig('fig_samesource_vs_independent.png'), y + Inches(0.20),
                Inches(3.60), max_w=Inches(6.5), left=X0)
    table(s, INDEPENDENT_ALL[['City', 'Map', 'Role', 'RMSE', 'MAE', 'Bias']],
          X0 + Inches(7.0), Inches(2.34), Inches(4.9), Inches(4.30), size=8.5)
    footnote(s, 'All fifteen maps, strict rule, 450 plots per city. The two '
                'axes are different references on different samples.')
    notes(s, """
This is the turn of the whole deck. Say the claim plainly: most of the
separation the same-source validation reported was agreement with CLMS rather
than accuracy.

Part of the collapse is a reshuffle, not only a compression. The worst map
differs between the two validations: the embeddings are last on the same-source
validation at 14.123, while on the independent one the S2 median is last at
25.984 and the embeddings sit third at 25.625. An ordering that survived three
metrics within the first validation does not survive the change of reference
intact.

On the left panel: the connecting lines trace each map's position within each
validation, not a change in its error. The two axes are different measurements
against different references on different samples — do not read a slope as an
improvement or a degradation.

In Vietnam the spread is wider and its structure different, because the maps
compared differ in kind rather than only in predictor set. In both cities the
two local retrains sit well ahead of both zero-shot maps — 26.502 and 27.282 in
Hanoi against 33.791 and 34.352 — reproducing the transfer conclusion against a
reference the models never saw.

HCMC is the exception, and the mechanism section accounts for it: the S2 median
zero-shot map records the city's best RMSE at 25.950, ahead of both local
retrains. That is about where the city's reference level falls relative to the
transferred map's level, not evidence that transfer succeeded. The embeddings
zero-shot map in the same city is the worst of all fifteen at 38.494.

Do not compare any number here with a same-source number. Different references,
different samples.
""")

    # ── Two tiers ────────────────────────────────────────────────────────────
    table_slide(
        prs, 'Independent validation · paired testing',
        'What survives is small but real: two tiers of two, not a clean '
        'ranking of four',
        'Paired Wilcoxon on per-plot absolute error, Milan, 450 plots, '
        'Benjamini-Hochberg within the city.',
        PAIRED, size=11,
        note='Between tiers q runs from 3.57e-08 to 6.84e-03; neither '
             'within-tier pair separates, both at q = 0.79.',
        say="""
The tiers: S2 stack with S2 percentile, and emb_RF with S2 median.
Indistinguishable within each tier, separated between them.

Two points need stating explicitly, because the previous slide showed
overlapping confidence intervals for these same maps.

First, the paired test and the confidence intervals measure different quantities
and both are correct. An interval describes the uncertainty of one map's RMSE
taken on its own, across resamples of the plots. The paired test compares two
maps on the same 450 plots, which removes the plot-level variance common to both
and therefore has more power to detect a consistent difference. Overlapping
intervals together with a significant paired difference is the expected
signature of a small but consistent difference, not a contradiction.

Second, the compression and the tier structure are both true. The spread falls
from 4.661 to 1.340, a compression of about 6.4 times — it shrinks sharply, it
does not vanish. What survives is small relative to each map's own error and
still resolvable across 450 paired plots. Neither half of that statement may be
dropped.

This analysis belongs to the independent validation, not to the Milan section:
it runs on per-plot absolute error against photo-interpretation, so placing it
beside the CLMS-scored holdout numbers would merge the two validations.

One non-result worth having ready: the paired test of S2_median_zeroshot against
S2_median_localrf in Hanoi reaches q = 0.063 and does not separate them. That is
not evidence the two are equivalent — absence of a detected difference is not a
demonstration of no difference — and nothing in the transfer argument rests on
that pair.
""")

    # ── Scatter grid ─────────────────────────────────────────────────────────
    picture_slide(
        prs, 'Independent validation',
        'Every registered map in all three cities, at plot level',
        'Photo-interpreted reference against predicted IMD, strict rule. The '
        'one place the scatter is shown rather than reduced to a metric.',
        fig('outputs_validation', 'fig01_scatter_grid.png'),
        max_h=Inches(4.5),
        say="""
The shape to point at: in the Vietnamese zero-shot panels the mass is held away
from the 1:1 line at low reference values. That is the distributional failure the
next section measures — the lost low tail.
""")

    # ── Training products ────────────────────────────────────────────────────
    picture_slide(
        prs, 'Independent validation · the diamonds',
        'Both training products score no better than the models fitted to them',
        'The diamonds mark CLMS and GHS-BUILT-S, scored here as maps under '
        'test rather than as targets, on the same 450 plots and the same terms '
        'as every model.',
        fig('outputs_validation', 'fig02_forest_ci.png'), max_h=Inches(3.95),
        note='What this measures is label quality, not a ceiling on achievable '
             'accuracy.',
        say="""
CLMS reaches an RMSE of 26.253 in Milan, worse than all four of the Milan models
it trained, the closest of which is the S2 median at 25.984. GHS-BUILT-S reaches
40.345 in Hanoi — worse than every map of any kind — and 37.355 in HCMC. Its
bias is +19.680 in Hanoi and +19.800 in HCMC, so it under-marks the interpreted
reference by close to 20 percentage points in both cities. That is the road
exclusion from the data section appearing as a number.

Be careful with what this means. It says the products these models were fitted
to disagree with careful photo-interpretation by about as much as the models
themselves do, which bears on where further gains are likely to come from. It
does not measure a ceiling on achievable model performance, and nothing here
should be read as one: a model is not confined to the accuracy of its labels.
The bias-recovery slide gives the mechanism and measures it.

The intervals are 95 % percentile bootstrap over 10 000 resamples of the 450
plots, the plot being the independent unit. The Milan intervals overlap one
another substantially, and the Milan models' intervals overlap CLMS's — which is
why the paired test, not the intervals, carries the tier result.

The tick on each RMSE bar is the noise-corrected RMSE, an upper bound.
""")

    # ── CLMS MAE vs RMSE ─────────────────────────────────────────────────────
    table_slide(
        prs, 'Independent validation · one apparent counter-example',
        'CLMS holds the best MAE of any Milan map and the worst RMSE, and both '
        'are correct',
        'Distribution of per-plot absolute error, Milan, strict rule, 450 '
        'plots.',
        ERROR_DIST, highlight_row=4, size=11,
        note='MAE and RMSE measure two halves of one trade rather than '
             'contradicting each other.',
        say="""
CLMS is right far more often than any model, landing within 5 percentage points
of the interpretation on 53.3 % of plots against 34.2 % for the closest model,
and wrong by more when it is wrong, carrying the largest share of gross errors
at 8.7 % of plots above 50 pp.

That is a product resolving each plot decisively where the models fitted to it
hedge. It costs the models where CLMS is nearly exact and saves them where it
fails badly. MAE rewards the first behaviour and RMSE penalises the second.

This is also the concrete case behind the metrics slide's warning that the two
can disagree about which of two maps is better, which is why both are reported
and neither is treated as a summary of the other.
""")

    # ── Rule sensitivity ─────────────────────────────────────────────────────
    table_slide(
        prs, 'Independent validation · robustness',
        'The conclusion does not depend on how the impervious classes are coded',
        'Milan RMSE under all three rules, with the resulting ranks. Rule B '
        'adds permeable pavement, rule C adds unpaved dirt road. Paved roads '
        'are impervious under all three.',
        RULE_SENSITIVITY, size=11.5,
        note='Under C the only change is a swap between the pair already found '
             'indistinguishable at q = 0.79.',
        say="""
Under rule B the ranking is unchanged. B reclassifies 23 cells across 6 plots in
Milan and C reclassifies 112 across 18, so B is much the smaller perturbation.
In Hanoi and HCMC the permeable-pavement code does not occur at all, so B is
identical to strict there by construction and only C differs.

Under rule C the top two maps and CLMS hold their positions, while emb_RF and S2
median exchange third and fourth: 23.03 against 22.98, a difference of 0.05. The
two maps that swap are exactly the pair the paired testing finds statistically
indistinguishable at q = 0.79, so the swap is a reordering within noise and not
a change of result.

All five Milan maps improve under rule C, by between 2.18 and 3.67 RMSE, and
CLMS is among them. Counting compacted dirt roads as impervious moves every map
closer to the reference, including the training target itself, which indicates
the disagreement rule C resolves is in the reference coding rather than in any
particular map.
""")

    # ═══════════════ SECTION 6 · Why transfer fails ══════════════════════════
    section_slide(prs, 6)

    # ── Mechanism one: level ─────────────────────────────────────────────────
    table_slide(
        prs, 'Mechanism · 1 of 2',
        'The transferred maps inherit Milan\'s level, and the retrains inherit '
        'GHSL\'s',
        'Mean predicted IMD against the interpreted reference mean, all eight '
        'Vietnamese maps. The two scenarios straddle the reference from '
        'opposite sides.',
        LEVELS, size=11,
        note='So which scenario scores better in a city depends partly on '
             'where that city\'s reference level falls between them.',
        say="""
Both zero-shot maps carry Milan's high level: 61.77 and 61.93 in Hanoi against a
reference mean of 46.05, and 70.70 and 57.89 in HCMC against 51.06. Both local
retrains inherit GHS-BUILT-S's low level, predicting between 37.87 and 39.97
across the two cities.

Note on the table: the report gives the four retrain means only as that range,
without assigning either endpoint to a specific city and map, so the rows carry
the range rather than a per-map value. The bias column is the
independent-validation bias.

This is the weaker of the two mechanisms — it is about where a distribution
sits, not what shape it has. The next-but-one slide gives the stronger one.
""")

    # ── HCMC consequence ─────────────────────────────────────────────────────
    table_slide(
        prs, 'Mechanism · the consequence',
        'Which is why HCMC\'s best map is a zero-shot map — and why that is '
        'not evidence transfer worked',
        'The four HCMC maps against photo-interpretation, strict rule.',
        HCMC_ROWS, highlight_row=0, size=11.5, t_w=Inches(9.5),
        note='A ranking that flips with the target city\'s level is a ranking '
             'set by level matching.',
        say="""
S2 median zero-shot records the city's best RMSE at 25.950, ahead of both local
retrains at 27.242 and 29.615. Its level gap is 6.83, the smallest of the four
HCMC maps, where the local retrains sit 11.09 and 12.23 below the reference.

The zero-shot map wins there because Milan's level happens to land closer to
HCMC's reference level than GHSL's does, not because the transfer worked.

In Hanoi, where the reference mean is lower at 46.05 and the zero-shot maps
overshoot by close to 16 points, the same two scenarios reverse and the local
retrains lead by six to eight RMSE.

That reversal between the two cities is the argument. If a ranking flips with
the target city's level, the ranking is set by level matching rather than by map
quality.
""")

    # ── Mechanism two: the lost tail ─────────────────────────────────────────
    picture_slide(
        prs, 'Mechanism · 2 of 2',
        'The low tail is gone, and no level correction could repair it',
        'Predicted IMD over the 450 HCMC plots for the four maps and the '
        'photo-interpreted reference, with each map\'s mean level marked.',
        fig('fig_hcmc_prediction_histogram.png'), max_h=Inches(4.05),
        note='The reference is bimodal; the embeddings zero-shot distribution '
             'is a narrow band with no low tail.',
        say="""
This is the stronger evidence, because it does not depend on level at all.

HCMC is the severe case and is shown here for that reason. The next slide shows
the same quantities for all eight maps across both cities, which is where the
mechanism is shown to generalise to Hanoi — do not let this slide stand alone as
if it were a one-city result.

Why no level correction could repair it: both references are strongly bimodal —
41.6 % of Hanoi plots below 10 % and 31.8 % above 90 %, 37.3 % and 35.8 % in
HCMC — and a map with no low tail cannot represent the lower mode wherever its
centre is placed. Shifting such a map downward would move its mass off the upper
mode without populating the lower one.

This is not a displaced distribution: a shifted map would keep its spread and
move only its centre.
""")

    # ── Tail and spread, all eight ───────────────────────────────────────────
    table_slide(
        prs, 'Mechanism · 2 of 2, both cities',
        'The tail is lost in Hanoi too, and every local retrain restores it',
        'Low-tail and spread retention for all eight Vietnamese maps, computed '
        'over the full predicted rasters: 8.4 million valid pixels in Hanoi, '
        '8.2 million in HCMC.',
        TAIL_SPREAD, size=11.5,
        note='Zero-shot embeddings retain 3.1 % of the reference\'s sub-20 % '
             'mass in Hanoi and 0.0 % in HCMC; the retrains retain 104–136 %.',
        say="""
This slide is where the mechanism generalises. The histogram was HCMC only; this
covers both cities and both predictor sets, and the pattern holds across all
eight maps.

Both embeddings zero-shot maps have lost the low tail. Below 10 % both rasters
are empty to four decimal places. The loss is a property of the transferred
embedding map rather than of one city, which is what makes it a mechanism rather
than an anecdote.

The two cities differ in how far the spread collapses alongside the tail. HCMC
holds 26 % of the reference interquartile range against Hanoi's 37 %, on IQRs of
26.0 and 37.4 against a reference IQR of 100.0, and its standard deviation is
15.95 against the reference's 44.81. HCMC is the severe case: the range has
narrowed around the missing tail as well as losing it. That severity shows in
the scores, where the HCMC embeddings zero-shot map is the worst of all fifteen
at 38.494 despite a mean of 70.70 that is not absurd for the city.

The complement: all four local retrains reach a raster floor of 0.00 and retain
between 104.0 % and 136.0 % of the sub-20 % mass — full recovery within the
precision this comparison supports. So: zero-shot transfer destroys the low end
of the distribution and local retraining restores it, in both cities and for
both predictor sets. That is the distributional counterpart of the R-squared
recovery.

The S2 median zero-shot maps sit between the two at 30.6 % and 68.7 %: degraded
rather than emptied. Consistent with both predictor sets failing while the
embeddings fail harder — but the composite-depth confound applies to that
contrast, so it is not a controlled comparison.

On reading the numbers: the tail figure compares a raster-wide share against a
450-plot share, so read it as an order of magnitude rather than to the
percentage point. A value at or above 100 % means the tail is fully present
rather than oversized.
""")

    # ── Bias recovery ────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Mechanism · what retraining recovers',
               'A model can score better than its own training target, and '
               'here it measurably does',
               'GHS-BUILT-S under-marks by 19.68 pp in Hanoi and 19.80 in '
               'HCMC. The models fitted to it are biased by only 6.59 to '
               '12.23, recovering 38 % to 67 % of the deficit.')
    add_picture(s, fig('fig_bias_recovery.png'), y + Inches(0.22),
                Inches(2.75))
    table(s, BIAS_RECOVERY, X0 + Inches(1.5), Inches(5.28), Inches(8.9),
          Inches(1.3), size=10.5)
    footnote(s, 'Bounded, not complete: a target that under-marks by 20 points '
                'still yields maps that under-mark by 7 to 12.')
    notes(s, """
This is the mechanism behind the training-product result, and it is what keeps
that result from meaning something it does not. The earlier slide showed the
training products score no better than the models fitted to them, and said that
measures label quality rather than a ceiling. This is why the two statements are
consistent.

Two mechanisms. Label error that is random from pixel to pixel cannot be fitted
by a model with limited capacity, so it is smoothed away rather than learned, and
the fitted surface lands closer to the truth than the individual labels do.
Systematic label error is different: GHS-BUILT-S's deficit is systematic,
arising from its exclusion of roads by design, yet the predictors still respond
to the sealed surfaces the target omits. A road GHS-BUILT-S does not mark is
still visible to the embeddings and to the Sentinel-2 reflectance percentiles,
and a model trained on plots where roads co-occur with marked built-up area
learns a response that partly recovers them.

Neither mechanism recovers the deficit fully, and the numbers say so: 38 % to
67 %, not 100 %. The residual bias of +6.59 to +12.23 is the part of the
target's systematic error the models do inherit.

Attribution: Žgela reports this effect qualitatively, observing that roads and
unroofed impervious surfaces are visibly better represented in the predicted
maps although still imperfectly, and that this highlights the model's ability to
recover information beyond what was explicitly provided during training. He
established it by visual inspection. Measuring it against an independent
reference is this project's contribution — his study had no means to do it.
""")

    # ═══════════════ SECTION 7 · Conclusions and limitations ═════════════════
    section_slide(prs, 7)

    # ── Conclusions ──────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Conclusions', 'Four answers')
    bullets(s, y + Inches(0.26), [
        ('1 · Composite choice',
         'Composite choice matters more than the foundation model on the '
         'same-source validation: percentile 9.462 against the embeddings\' '
         '14.123, a 33 % reduction, with the same ordering on RMSE, MAE and '
         'R². The advantage is mechanistically interpretable — B4_p25 carries '
         'a permutation importance of 0.1812, more than three times the next '
         'band.'),
        ('2 · The compression',
         'Against an independent reference the four-way spread compresses '
         'about 6.4-fold, from 33.0 % to 5.2 % of the worst map, yet paired '
         'testing still resolves two tiers. Same-source validation is the '
         'right instrument for model selection and the wrong one for claiming '
         'accuracy: reporting a 33 % same-source reduction as a 33 % gain in '
         'accuracy would misdescribe it by a factor of six.'),
        ('3 · Transfer',
         'Zero-shot transfer fails — R² at or below zero in three of four '
         'combinations — and local retraining is necessary, recovering R² to '
         '0.522–0.649. It is not uniformly better: above 80 % imperviousness '
         'it is worse.'),
        ('4 · The targets',
         'The training products are not ceilings. CLMS scores 26.253 and '
         'GHS-BUILT-S 40.345 and 37.355, in each case no better than the '
         'models fitted to them. That measures label quality; the models '
         'recover 38–67 % of GHSL\'s systematic deficit.'),
    ], size=12, head_w=Inches(2.5), step=Inches(1.18))
    notes(s, """
The two that qualify each other are 1 and 2. A reader who takes the first
without the second will overstate what the study shows — that is exactly the
failure this deck is built to prevent.

The reshuffle belongs with conclusion 2: the S2 median is last on the
independent validation at 25.984 where the embeddings were last on the
same-source one at 14.123. The ordering is partly reshuffled, not merely
compressed.

Conclusion 3's mechanisms: level inheritance, and the lost low tail — 3.1 % of
the sub-20 % mass retained in Hanoi and 0.0 % in HCMC, restored to 104–136 % by
every local retrain. And the honest caveat that retraining costs accuracy above
80 %: C6 MAE rises from 17.25 to 30.95 in Hanoi and 12.93 to 25.20 in HCMC.

Conclusion 4 bounded: retraining on a product that under-marks by roughly 20
points still yields maps that under-mark by 7 to 12.
""")

    # ── Limitations ──────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Limitations',
               'Five constraints, each with the conclusion it forbids')
    bullets(s, y + Inches(0.22), [
        ('Composite depth',
         'Confounded with predictor type in Vietnam: the embeddings arm '
         'compares annual against annual, the Sentinel-2 arm a 30-date '
         'composite against 3 or 4 dates. Forbids any statement that one '
         'predictor set transfers better than the other.'),
        ('Plot independence',
         'Assumed and untested. If residual autocorrelation is present the '
         'effective sample is below 450, the bootstrap intervals are too '
         'narrow and the paired q values are optimistic. The tier structure is '
         'supported; its weakest pair is not established at the quoted '
         'precision.'),
        ('RMSE_corr',
         'An upper bound on map error, not a point estimate. The claim that '
         'any Milan map achieves an error of 21.559 is not supported; that '
         'they lie between 21.559 and 22.917 corrected is a statement about '
         'bounds.'),
        ('One interpreter',
         'All 1 350 plots were interpreted by one analyst under one reading of '
         'the rules, with no inter-rater estimate. Paired within-city '
         'differences are less exposed; absolute error levels, the intervals '
         'and the bias measurements carry the component in full.'),
        ('Stratified plots',
         'Plots are stratified by the product under test, not drawn at random '
         'over the city, and no area weights are applied. Comparisons between '
         'maps hold. What would be wrong is that any RMSE here describes the '
         'accuracy of a map over its city.'),
    ], size=11.5, head_w=Inches(2.3), step=Inches(0.98))
    notes(s, """
Each is stated with the conclusion it forbids, because a limitation that does
not change a reading of the results is not worth recording.

On the interpreter caveat, the scope is narrow and should not be widened.
Because the paired tests difference two maps plot by plot against the same
interpreted value, an interpretation tendency that displaces a plot's reference
value affects both maps in the pair and drops out of that difference. No such
cancellation applies anywhere else: the absolute RMSE and MAE levels, the
bootstrap intervals and the bias measurements each score a map against the
reference rather than against another map. Nor does the shared reference protect
the rankings — a tendency that displaces the reference by different amounts in
different kinds of plot penalises maps unequally. The single claim it supports is
that paired within-city differences are less exposed than the error levels are.

On the stratification: strata occupying a small share of the urban area are
represented as heavily as strata occupying a large one, and the bimodality of
the Vietnamese references is a property of the plot sample, not necessarily of
the cities.

The two worth flagging in advance if the discussion runs long are composite
depth and stratification, because they limit comparisons someone might otherwise
expect this work to make.
""")

    prs.save(OUT_PPTX)
    return prs


if __name__ == '__main__':
    deck = build()
    n = len(deck.slides._sldIdLst)
    print(f'Wrote {OUT_PPTX}  ({n} slides, {len(SECTIONS)} sections)')
