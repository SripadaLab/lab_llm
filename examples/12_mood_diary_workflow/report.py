"""Render the final workflow artifacts as one standalone HTML report."""

from html import escape
from pathlib import Path


def render_report(themes, scores, evidence, path: Path) -> None:
    """Join strict scores and separate evidence into a readable report."""
    theme_by_id = {theme["theme_id"]: theme for theme in themes}
    evidence_by_id = {item["theme_id"]: item for item in evidence}
    cards = []

    for score in scores:
        theme = theme_by_id[score["theme_id"]]
        audit = evidence_by_id.get(score["theme_id"])
        quotes = ""
        if audit:
            quotes = "".join(
                "<blockquote>"
                f"{escape(quote['text'])}"
                f"<cite>{escape(quote['date'])}</cite>"
                "</blockquote>"
                for quote in audit["quotes"]
            )

        explanation = (
            escape(audit["explanation"])
            if audit else "Evidence audit not requested for this theme."
        )
        cards.append(f"""
        <article class="theme-card">
          <div class="rank">{score['rank']:02d}</div>
          <div class="theme-main">
            <div class="theme-heading">
              <div>
                <p class="eyebrow">{escape(score['theme_id'])}</p>
                <h2>{escape(theme['title'])}</h2>
              </div>
              <div class="score">{score['salience']:.1f}</div>
            </div>
            <p class="description">{escape(theme['description'])}</p>
            <div class="metrics">
              <span><strong>{score['diary_count']}</strong> diary days</span>
              <span><strong>{score['candidate_count']}</strong> mentions</span>
              <span><strong>{score['mean_importance']:.1f}</strong> mean importance</span>
            </div>
            <div class="audit">
              <h3>Evidence audit</h3>
              <p>{explanation}</p>
              {quotes}
            </div>
          </div>
        </article>""")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mood Diary Theme Report</title>
  <style>
    :root {{ --ink:#172434; --muted:#627386; --blue:#0b607b;
      --pale:#eef7fa; --line:#d8e4ea; --gold:#db9b36; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:#f5f8fa;
      font:16px/1.55 Inter,ui-sans-serif,system-ui,sans-serif; }}
    header {{ padding:72px max(7vw,32px) 54px; color:white;
      background:linear-gradient(130deg,#10273b,#0b607b 72%,#1687a2); }}
    header p {{ max-width:760px; margin:12px 0 0; color:#d8edf4; font-size:19px; }}
    h1 {{ max-width:900px; margin:0; font-size:clamp(38px,6vw,72px);
      line-height:1.02; letter-spacing:-.04em; }}
    main {{ width:min(1060px,calc(100% - 40px)); margin:44px auto 80px; }}
    .summary {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px;
      margin-bottom:30px; }}
    .summary div {{ padding:20px; border:1px solid var(--line); border-radius:16px;
      background:white; }}
    .summary strong {{ display:block; font-size:28px; color:var(--blue); }}
    .theme-card {{ display:grid; grid-template-columns:72px 1fr; gap:22px;
      margin:18px 0; padding:28px; background:white; border:1px solid var(--line);
      border-radius:20px; box-shadow:0 14px 40px rgba(30,60,78,.07); }}
    .rank {{ width:58px; height:58px; display:grid; place-items:center; border-radius:16px;
      color:white; background:var(--blue); font-size:22px; font-weight:800; }}
    .theme-heading {{ display:flex; justify-content:space-between; gap:20px; }}
    .eyebrow {{ margin:0 0 4px; color:var(--blue); font-weight:800;
      text-transform:uppercase; letter-spacing:.12em; font-size:12px; }}
    h2 {{ margin:0; font-size:30px; letter-spacing:-.025em; }}
    .score {{ min-width:72px; text-align:right; color:var(--gold);
      font-size:34px; font-weight:850; }}
    .description {{ color:var(--muted); font-size:18px; }}
    .metrics {{ display:flex; flex-wrap:wrap; gap:9px; margin:20px 0; }}
    .metrics span {{ padding:8px 11px; border-radius:999px; background:var(--pale); }}
    .audit {{ margin-top:22px; padding-top:20px; border-top:1px solid var(--line); }}
    .audit h3 {{ margin:0 0 6px; }}
    blockquote {{ margin:12px 0; padding:14px 18px; border-left:4px solid var(--gold);
      background:#fffaf1; border-radius:0 10px 10px 0; }}
    cite {{ display:block; margin-top:7px; color:var(--muted); font-style:normal; font-size:13px; }}
    @media (max-width:700px) {{ .summary {{ grid-template-columns:1fr; }}
      .theme-card {{ grid-template-columns:1fr; }} .theme-heading {{ align-items:flex-start; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Mood diary life themes</h1>
  </header>
  <main>
    <section class="summary">
      <div><strong>{len(scores)}</strong>canonical themes</div>
      <div><strong>{sum(item['candidate_count'] for item in scores)}</strong>candidate mentions</div>
      <div><strong>{len(evidence)}</strong>evidence audits</div>
    </section>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
