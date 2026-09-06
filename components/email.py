import os

import pandas as pd
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException


# Keep provider credentials and email addresses outside source code.
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
BREVO_COPY_EMAIL = os.getenv("BREVO_COPY_EMAIL")

configuration = sib_api_v3_sdk.Configuration()
if BREVO_API_KEY:
    configuration.api_key["api-key"] = BREVO_API_KEY

api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
    sib_api_v3_sdk.ApiClient(configuration)
)


def send_email(to_email: str, df: pd.DataFrame):
    """Send an email listing the lowest-scoring students in ``df``."""
    if not BREVO_API_KEY or not BREVO_SENDER_EMAIL:
        raise RuntimeError(
            "BREVO_API_KEY and BREVO_SENDER_EMAIL must be configured to send email."
        )

    count = len(df)
    if "overall_score" in df.columns:
        df = df.copy()
        df["overall_score"] = df["overall_score"].astype(str) + "%"
        df["Status"] = "Low Performer"

    email_subject = "Attention Is All You(r Students) Need"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><style>
      body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.4; font-size: 14px; }}
      .data-table {{ border-collapse: collapse; width: 80%; margin-bottom: 30px; }}
      .data-table th, .data-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
      .data-table th {{ background-color: #f4f4f4; }}
    </style></head>
    <body>
      <p>
        Hello Teacher,<br><br>
        These are the {count} lowest-scoring students that have been found to require extra guidance.<br>
        More details can be found in the AI-Enhanced Personalized Student Support.
      </p>
      <table class="data-table">
        <tr>
          {' '.join(f'<th>{col}</th>' for col in df.columns)}
        </tr>
        {''.join('<tr>' + ''.join(f'<td>{row[col]}</td>' for col in df.columns) + '</tr>' for _, row in df.iterrows())}
      </table>
      <p>For the full report and to explore suggested interventions, open the application:</p>
      <p>http://localhost:8501</p>
    </body>
    </html>
    """

    recipients = [{"email": to_email}]
    if BREVO_COPY_EMAIL:
        recipients.append({"email": BREVO_COPY_EMAIL})

    message = sib_api_v3_sdk.SendSmtpEmail(
        to=recipients,
        sender={"email": BREVO_SENDER_EMAIL},
        subject=email_subject,
        html_content=html_body,
    )

    try:
        api_response = api_instance.send_transac_email(message)
        print("Email sent! Message ID:", api_response.message_id)
        return True
    except ApiException as e:
        print(f"Error sending email: {e}")
        return False
