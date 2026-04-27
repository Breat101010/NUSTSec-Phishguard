import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- MAILTRAP CONFIGURATION ---
SMTP_HOST = "sandbox.smtp.mailtrap.io"
SMTP_PORT = 2525
SMTP_USER = "2eec9d32f99edc"
SMTP_PASS = "249e6151b2e13a"
SENDER_EMAIL = "security@nustsec.co.zw"

def send_phishing_email(target_email, template_name, tracking_token):
    # 1. Create unique, weaponized tracking link
    tracking_link = f"http://127.0.0.1:8000/click/{tracking_token}"

    # 2. Load localized African templates
    if template_name == "mukuru_verification":
        subject = "URGENT: Mukuru Transfer Intercepted"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #ff6600;">Mukuru Security Alert</h2>
                <p>Dear Customer,</p>
                <p>Your recent cross border transfer has been temporarily suspended due to a security flag.</p>
                <p>Please verify your recipient details immediately to release the funds:</p>
                <br>
                <a href="{tracking_link}" style="display: inline-block; padding: 10px 20px; background-color: #ff6600; color: white; text-decoration: none; border-radius: 5px;">Verify Transfer Now</a>
                <br><br>
                <p><small>If you do not recognize this activity, please ignore this email.</small></p>
            </body>
        </html>
        """
    elif template_name == "zesa_token_error":
        subject = "ZESA: Token Generation Failed"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #0033a0;">ZESA Prepaid Alert</h2>
                <p>Your recent prepaid token purchase failed to sync with your meter.</p>
                <a href="{tracking_link}" style="display: inline-block; padding: 10px 20px; background-color: #0033a0; color: white; text-decoration: none; border-radius: 5px;">Click here to manually retrieve your 20-digit token</a>
            </body>
        </html>
        """
    else:
        subject = "Security Update"
        html_content = f"<p>Please review your account: <a href='{tracking_link}'>Click Here</a></p>"

    # 3. Build email payload
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = target_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))

    # 4. Send the Payload via Mailtrap
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[+] SUCCESS: Sent'{template_name}' payload to {target_email}")
    except Exception as e:
        print(f"[-] ERROR: Failed to send to {target_email}. Reason: {e}")