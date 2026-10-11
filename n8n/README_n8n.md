# n8n integration: sending approved emails

LeadPilot's agents never send email themselves. After a human approves drafts in the app, the app posts them to this n8n workflow, which sends them through SMTP (session 16-17: webhook + SMTP nodes).

**Flow:** LeadPilot app → POST JSON → n8n **Webhook** → **Split Out** (one item per email) → **Send Email (SMTP)**

## Setup (about 10 minutes)
1. Start n8n: `npx n8n` (needs Node.js) or use n8n cloud. Open http://localhost:5678
2. **Workflows → Import from File →** choose `leadpilot_send_approved_emails.json`
3. Open the **Send Email (SMTP)** node:
   - Create an SMTP credential. For Gmail: host `smtp.gmail.com`, port `465`, SSL on, user = your Gmail, password = a Gmail **App Password** (Google Account → Security → 2-Step Verification → App passwords).
   - Replace `YOUR_EMAIL@gmail.com` in *From Email* with your Gmail.
4. Open the **Webhook** node and copy the **Test URL** (`http://localhost:5678/webhook-test/leadpilot`). Click **Listen for test event**.
5. In the LeadPilot app → **Outreach approval** tab: paste the URL, enter **your own email** as the demo recipient, approve a few drafts, click **Send approved emails via n8n**.
6. Check your inbox. To keep it running without clicking "Listen", toggle the workflow **Active** and use the **Production URL** (`/webhook/leadpilot`).

**Safety:** in demo mode every email goes to the demo recipient you enter (the sample prospects are fictional), and each email is labelled with the prospect it was written for.

## Payload the app sends
```json
{"emails": [{"to": "you@gmail.com", "subject": "...", "email_body": "...", "lead_id": "L001",
             "company": "Brightline Logistics", "contact": "Ananya Mehta", "owner": "Aditi Rao"}]}
```
