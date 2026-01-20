import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
from dotenv import load_dotenv

class Notifier:
    def __init__(self):
        load_dotenv()
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)

    def send_report_email(self, to_email: str, job_id: str, results_summary: Dict):
        """Send a summary report and download link"""
        if not self.smtp_user or not self.smtp_pass:
            print("[NOTIFY] ⚠️ SMTP credentials missing. Email skipped.")
            return False

        subject = f"AnyROR Scrape Complete: Job {job_id}"
        
        body = f"""
        <h3>AnyROR Scrape Summary</h3>
        <p><b>Job ID:</b> {job_id}</p>
        <p><b>District:</b> {results_summary.get('district', 'N/A')}</p>
        <p><b>Total Villages:</b> {results_summary.get('total', 0)}</p>
        <p><b>Hits Found:</b> {results_summary.get('hits', 0)}</p>
        <hr>
        <p>You can view the full report on your dashboard or download the raw data here:</p>
        <p><a href="https://yourportal.com/reports/{job_id}">View Report</a></p>
        <br>
        <p><i>Automated System - AnyROR Scraper Turbo</i></p>
        """

        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
                print(f"[NOTIFY] ✓ Report sent to {to_email}")
                return True
        except Exception as e:
            print(f"[NOTIFY] ❌ Failed to send email: {e}")
            return False

if __name__ == "__main__":
    # Test notification
    n = Notifier()
    n.send_report_email("test@example.com", "JOB-123", {"district": "Kachchh", "total": 400, "hits": 15})
