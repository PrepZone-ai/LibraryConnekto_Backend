"""Shared HTML layout for Library Connekto transactional emails (consistent header/footer and accessibility-friendly CTAs)."""

from __future__ import annotations

import html


def _h(s: str) -> str:
    return html.escape(s or "", quote=False)


def _ha(s: str) -> str:
    return html.escape(s or "", quote=True)


def standard_transactional_shell(
    *,
    document_title: str,
    preheader: str,
    header_badge: str,
    headline: str,
    tagline: str,
    main_inner_html: str,
) -> str:
    """Table-based wrapper: works reliably across common email clients."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{_h(document_title)}</title>
</head>
<body style="margin:0;padding:0;background-color:#e8edf4;-webkit-text-size-adjust:100%;">
  <span style="display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;max-height:0;max-width:0;overflow:hidden;mso-hide:all;">{_h(preheader)}</span>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#e8edf4;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(15,39,68,0.12);">
          <tr>
            <td style="background:linear-gradient(135deg,#1a365d 0%,#2c5282 45%,#2d5a87 100%);padding:36px 32px;text-align:center;">
              <p style="margin:0 0 10px 0;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:11px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.88);">{_h(header_badge)}</p>
              <p style="margin:0 0 14px 0;font-family:Georgia,'Times New Roman',serif;font-size:15px;font-weight:600;letter-spacing:0.25em;color:rgba(255,255,255,0.95);">LIBRARY</p>
              <h1 style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:26px;line-height:1.25;font-weight:600;color:#ffffff;">{_h(headline)}</h1>
              <p style="margin:12px 0 0 0;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.5;color:rgba(255,255,255,0.92);">{_h(tagline)}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 32px;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:16px;line-height:1.65;color:#2d3748;">
              {main_inner_html}
            </td>
          </tr>
          <tr>
            <td style="padding:28px 32px 32px 32px;background-color:#f7fafc;border-top:1px solid #e2e8f0;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:13px;line-height:1.6;color:#4a5568;">
              <p style="margin:0 0 12px 0;"><strong style="color:#2d3748;">Library Connekto</strong><br>Library Management System</p>
              <p style="margin:0 0 12px 0;">This is an automated transactional message. Please do not reply directly to this email—replies are not monitored.</p>
              <p style="margin:0 0 12px 0;color:#718096;">If you did not request this email, you can safely ignore it. No changes will be made to your account.</p>
              <p style="margin:0;font-size:12px;color:#a0aec0;">© Library Connekto</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def cta_button_block(href: str, label: str) -> str:
    """Primary CTA: high contrast (WCAG-friendly) for link-styled buttons in clients."""
    return f"""<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:24px 0;">
  <tr>
    <td align="left">
      <a href="{_ha(href)}" style="display:inline-block;padding:14px 28px;background-color:#2b6cb0;color:#ffffff!important;font-weight:600;font-size:16px;text-decoration:none;border-radius:8px;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;line-height:1.2;mso-padding-alt:0;">{_h(label)}</a>
    </td>
  </tr>
</table>"""


def fallback_link_block(url: str) -> str:
    return f"""<p style="margin:24px 0 8px 0;font-size:14px;color:#4a5568;">If the button does not work, copy and paste this link into your browser:</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0;">
  <tr>
    <td style="padding:14px 16px;background-color:#edf2f7;border-radius:8px;border:1px solid #cbd5e0;font-family:Consolas,'Courier New',monospace;font-size:12px;line-height:1.5;word-break:break-all;">
      <a href="{_ha(url)}" style="color:#1e40af;text-decoration:underline;">{_h(url)}</a>
    </td>
  </tr>
</table>"""


def notice_box(inner_html: str) -> str:
    return f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:28px;">
  <tr>
    <td style="padding:16px 18px;background-color:#fffaf0;border:1px solid #ecc94b;border-radius:8px;font-size:14px;line-height:1.55;color:#744210;">
      {inner_html}
    </td>
  </tr>
</table>"""


def standard_footer_plain() -> str:
    return """
---
Library Connekto · Library Management System
This is an automated message; please do not reply.
If you did not request this email, you can ignore it safely.
"""
