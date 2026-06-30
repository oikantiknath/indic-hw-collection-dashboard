"""Chart layout helper, section header, badge, progress bar.

All functions that reference theme variables (_dark, _text, etc.) accept a
`theme` dict so they stay decoupled from app.py globals.
"""

import streamlit as st

CHART_HEIGHT = 300

# ── Color palette ──────────────────────────────────────────────────────────────
C_GREEN   = "#34D399"
C_RED     = "#F87171"
C_AMBER   = "#FBBF24"
C_GREY    = "#6B7280"
C_FEMALE  = "#C084FC"
C_MALE    = "#60A5FA"
C_GOVT    = "#34D399"
C_AIDED   = "#6EE7B7"
C_PRIVATE = "#F43F5E"
C_RURAL   = "#34D399"
C_URBAN   = "#2563eb"
C_LEFT    = "#C084FC"
C_RIGHT   = "#60A5FA"
C_INDIGO  = "#d4500a"
C_VIOLET  = "#b45309"

COLORS = [
    "#d4500a", "#34D399", "#FBBF24", "#C084FC", "#60A5FA",
    "#b45309", "#6EE7B7", "#F9A8D4", "#FCD34D", "#7DD3FC",
]


def make_chart_layout(theme: dict):
    """Return a chart_layout(**kwargs) function bound to the given theme dict."""
    _text        = theme["text"]
    _text2       = theme["text2"]
    _bg2         = theme["bg2"]
    _border      = theme["border"]
    _template    = "plotly_white"
    _grid_clr    = "rgba(0,0,0,0.08)"
    _chart_text  = _text
    _bar_textfont = dict(color=_text, family="Inter", size=11)

    _axis_title_font = dict(color=_chart_text, family="Inter", size=12)
    _axis_tick_font  = dict(color=_chart_text, family="Inter", size=11)

    def chart_layout(**kwargs):
        title_str = kwargs.pop("title", "")
        base = dict(
            template=_template,
            height=kwargs.pop("height", CHART_HEIGHT),
            margin=dict(l=40, r=20, t=50, b=55),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            title=dict(text=title_str, font=dict(size=15, color=_text, family="Inter")),
            font=dict(family="Inter", size=12, color=_chart_text),
            xaxis=dict(
                showgrid=False, zeroline=False,
                showline=True, linecolor=_grid_clr, linewidth=1,
                color=_chart_text,
                tickfont=_axis_tick_font,
                title=dict(font=_axis_title_font),
            ),
            yaxis=dict(
                showgrid=True, gridcolor=_grid_clr, zeroline=False,
                showline=True, linecolor=_grid_clr, linewidth=1,
                color=_chart_text,
                tickfont=_axis_tick_font,
                title=dict(font=_axis_title_font),
            ),
            legend=dict(font=dict(color=_chart_text)),
            hoverlabel=dict(bgcolor=_bg2, font_color=_text, font_size=13,
                            font_family="Inter", bordercolor=_border),
        )
        base.update(kwargs)
        return base

    return chart_layout, _bar_textfont


def section(title: str):
    anchor = title.lower().replace(" ", "-").replace("&", "and")
    st.markdown(f'<div id="{anchor}" class="section-header">{title}</div>', unsafe_allow_html=True)


def badge(label: str, passed: bool) -> str:
    cls = "badge-pass" if passed else "badge-fail"
    return f'<span class="{cls}">{label}</span>'


def progress_bar_html(label, current, target, fmt_current="", fmt_target="",
                      override_color=None, target_pct=None, theme: dict | None = None):
    _text  = (theme or {}).get("text",  "#0F172A")
    _text2 = (theme or {}).get("text2", "#64748B")
    _text3 = (theme or {}).get("text3", "#1E293B")
    _bg2   = (theme or {}).get("bg2",   "#FFFFFF")
    _border_card = (theme or {}).get("border_card", "rgba(0,0,0,0.08)")
    _progress_track = (theme or {}).get("progress_track", "rgba(0,0,0,0.08)")

    pct = min(current / target * 100, 100) if target else 0
    if override_color:
        color = override_color
    elif pct >= 100:
        color = "#10B981"
    elif pct >= 60:
        color = "#F59E0B"
    else:
        color = "#F43F5E"

    fmt_c = fmt_current or f"{current:,}"
    fmt_t = fmt_target  or f"{target:,}"
    target_line = ""
    if target_pct is not None:
        target_line = (
            f"<div style='position:absolute;left:{target_pct}%;top:0;bottom:0;"
            f"width:2px;background:#F59E0B;border-radius:2px;'></div>"
        )
    return f"""
<div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:12px 16px;margin-bottom:8px;'>
  <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;'>
    <span style='font-size:0.82rem;font-weight:600;color:{_text3};'>{label}</span>
    <span style='font-size:0.78rem;font-weight:700;color:{color};'>{pct:.1f}%</span>
  </div>
  <div style='position:relative;background:{_progress_track};border-radius:6px;height:8px;overflow:visible;margin-bottom:5px;'>
    <div style='width:{pct:.1f}%;background:{color};height:100%;border-radius:6px;
                box-shadow:0 0 6px {color}55;transition:width 0.5s;'></div>
    {target_line}
  </div>
  <div style='display:flex;justify-content:space-between;'>
    <span style='font-size:0.72rem;color:{_text2};'>{fmt_c}</span>
    <span style='font-size:0.72rem;color:{_text2};'>{fmt_t}</span>
  </div>
</div>"""
