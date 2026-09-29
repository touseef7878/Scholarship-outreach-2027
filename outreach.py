import argparse
import os
import re
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

import config
from gmail_service import get_service, build_message, create_draft, send_message

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ---------------------------------------------------------------------------
# Applicant profile — injected into the AI prompt only
# ---------------------------------------------------------------------------
APPLICANT_PROFILE = """
Name: Touseef Ur Rehman
Degree: BS Computer Science, HITEC University, Pakistan
CGPA: 3.27/4.00
Research interests: Machine Learning, Deep Learning, Computer Vision, Data Science, NLP, Intelligent Systems
FYP: OceanGuard AI
  - Object detection component: YOLO26s model trained on ~16,500 marine-debris images (images and recorded videos)
  - Forecasting component: LSTM/GRU models for ocean-pollution trend prediction
Goal: Fully funded Master's in China for the 2027 intake (Chinese Government Scholarship / university scholarships)
""".strip()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data():
    df = pd.read_csv(config.DATASET, dtype=str).fillna("")
    for col in ["Email_Status", "Date_Contacted", "Follow_Up_Date", "Reply_Status",
                "Gmail_Draft_ID", "Gmail_Message_ID", "Last_Error"]:
        if col not in df.columns:
            df[col] = ""
    return df


def save_data(df):
    df.to_csv(config.DATASET, index=False, encoding="utf-8-sig")


def valid_email(v):
    return bool(EMAIL_RE.match(str(v).strip()))


def eligible(df):
    status = df["Email_Status"].str.strip().str.lower()
    return df[df["Public_Email"].apply(valid_email) &
              ~status.isin(["draft created", "sent", "replied"])]


# ---------------------------------------------------------------------------
# Groq AI — generates ONLY the opening hook (2-3 sentences)
# ---------------------------------------------------------------------------

def _groq_client():
    load_dotenv()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not found. Make sure your .env file contains:\n"
            "GROQ_API_KEY=your_key_here"
        )
    from groq import Groq
    return Groq(api_key=api_key)


def _generate_hook(client, professor: str, university: str,
                   research_areas: str, fit_notes: str,
                   fyp_connection: str) -> str:
    """
    Generate a 2-3 sentence personalised opening hook for this specific professor.
    This is the ONLY part written by AI. The rest of the email is the fixed template.
    """
    prompt = f"""You are writing the opening 2-3 sentences of a cold outreach email from a graduate student to a professor.

This short hook must:
1. Open with a genuine, specific observation about the professor's research — name their actual research area
2. In the same breath or next sentence, naturally connect it to the student's FYP project (OceanGuard AI) or background
3. Feel human-written, direct, and confident — NOT like a template
4. Be 2-3 sentences maximum — concise and punchy
5. NOT start with "I am writing to", "I came across", "I hope this email finds you", or any cliché opener
6. NOT include any greeting, salutation, sign-off, or subject line
7. Every sentence must be complete — do not trail off mid-thought
8. Output ONLY the hook text, nothing else

Professor: {professor}
University: {university}
Research areas: {research_areas}
Why this professor fits the applicant: {fit_notes}
How the FYP connects to this professor's work: {fyp_connection}

Applicant background:
{APPLICANT_PROFILE}
"""
    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.75,
        max_tokens=200,
    )
    hook = response.choices[0].message.content
    # Handle None or whitespace
    if hook is None:
        hook = ""
    hook = hook.strip()

    # Remove any <think>...</think> tags that reasoning models sometimes emit
    import re as _re
    hook = _re.sub(r"<think>.*?</think>", "", hook, flags=_re.DOTALL).strip()

    # Safety: if the hook is suspiciously short, raise so caller can retry
    if len(hook) < 40:
        raise ValueError(f"Hook too short ({len(hook)} chars): {repr(hook)}")

    # If it ends mid-sentence (trailing comma, semicolon, or conjunction), raise to retry
    last_char = hook[-1] if hook else ""
    if last_char in ",;":
        raise ValueError(f"Hook appears cut off (ends with {repr(last_char)}): {repr(hook[-50:])}")

    return hook


def _build_email_body(professor: str, hook: str, row: pd.Series) -> str:
    """
    Assemble the full email from the AI hook + the original CSV fields.
    The hook replaces only Professor_Specific_Opening.
    All other paragraphs come directly from the CSV (unchanged human-written content).
    """
    fyp_para   = row["FYP_Research_Connection"].strip()
    ask        = row["Personalized_Ask"].strip()

    # If FYP connection is blank in CSV, fall back to the generic one from Generated_Email_Body
    if not fyp_para:
        fyp_para = (
            "My final-year project, OceanGuard AI, uses a YOLO26s model trained on about "
            "16,500 marine-debris images for object detection in recorded images/videos; "
            "this gives me a direct practical foundation in visual recognition and deep learning."
        )

    return (
        f"Dear Professor {professor},\n"
        f"\n"
        f"{hook}\n"
        f"\n"
        f"My name is Touseef Ur Rehman, a BS Computer Science graduate from HITEC University, "
        f"Pakistan, with a CGPA of 3.27/4.00. My research interests include Machine Learning, "
        f"Deep Learning, Computer Vision, Data Science, NLP, and Intelligent Systems.\n"
        f"\n"
        f"I am preparing applications for fully funded Master's opportunities in China for the "
        f"2027 intake, including Chinese Government Scholarship and relevant university scholarship "
        f"routes. {ask}\n"
        f"\n"
        f"I have attached my academic CV for your consideration. I would be happy to provide my "
        f"transcript, degree documents, English Proficiency Certificate, research proposal, or any "
        f"additional information you may require.\n"
        f"\n"
        f"Thank you very much for your time and consideration.\n"
        f"\n"
        f"Best regards,\n"
        f"Touseef Ur Rehman\n"
        f"BS Computer Science, HITEC University, Pakistan\n"
        f"Email: touseefurrehman5554@gmail.com\n"
        f"Portfolio: https://touseef.eu.cc/\n"
        f"GitHub: https://github.com/touseef7878\n"
        f"LinkedIn: https://linkedin.com/in/touseef123"
    )


# ---------------------------------------------------------------------------
# Enhance command
# ---------------------------------------------------------------------------

def enhance(df, count, preview_only=False):
    """
    Use Groq AI to write a personalised opening hook for each eligible professor,
    then rebuild Generated_Email_Body using the hook + original CSV fields.
    """
    targets = eligible(df).head(count)
    if targets.empty:
        print("No eligible records to enhance.")
        return df

    try:
        client = _groq_client()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return df

    for idx, r in targets.iterrows():
        professor     = r["Professor"].strip()
        university    = r["University"].strip()
        research_areas = r["Research_Areas"].strip()
        fit_notes     = (r.get("Fit_to_Touseef", "") + " " +
                         r.get("Personalization_Angle", "")).strip()
        fyp_connection = r.get("FYP_Research_Connection", "").strip()

        print(f"Enhancing: {professor} <{r['Public_Email']}>", end=" ... ", flush=True)

        # Retry up to 3 times if hook is truncated or empty
        hook = None
        for attempt in range(3):
            try:
                hook = _generate_hook(client, professor, university,
                                      research_areas, fit_notes, fyp_connection)
                break
            except ValueError as e:
                if attempt < 2:
                    import time; time.sleep(2)
                    print(f"(retrying — {e})", end=" ", flush=True)
                else:
                    print(f"ERROR: Hook failed after 3 attempts. Skipping.")
                    hook = None
            except Exception as e:
                print(f"ERROR: {e}")
                df.at[idx, "Last_Error"] = str(e)[:500]
                hook = None
                break

        if hook is None:
            continue

        new_body = _build_email_body(professor, hook, r)

        if preview_only:
            print("done")
            print("\n" + "=" * 80)
            print(f"TO      : {r['Public_Email']}")
            print(f"SUBJECT : {r['Personalized_Email_Subject']}")
            print("-" * 80)
            print(new_body)
            print()
        else:
            df.at[idx, "Professor_Specific_Opening"] = hook
            df.at[idx, "Generated_Email_Body"] = new_body
            save_data(df)
            print("done")

    return df


# ---------------------------------------------------------------------------
# Preview (uses current CSV content, no AI)
# ---------------------------------------------------------------------------

def preview(df, n=5):
    subset = eligible(df).head(n)
    if subset.empty:
        print("No eligible unsent records.")
        return
    for _, r in subset.iterrows():
        print("\n" + "=" * 80)
        print(f"TO: {r['Public_Email']}")
        print(f"PROFESSOR: {r['Professor']} | {r['University']}")
        print(f"SUBJECT: {r['Personalized_Email_Subject']}")
        print("-" * 80)
        print(r["Generated_Email_Body"])


# ---------------------------------------------------------------------------
# Draft / Send
# ---------------------------------------------------------------------------

def process(df, count, do_send=False):
    targets = eligible(df).head(count)
    if targets.empty:
        print("No eligible unsent records.")
        return df
    if do_send and not config.ALLOW_SEND:
        raise RuntimeError(
            "Sending is locked. Set ALLOW_SEND=True in config.py only after reviewing drafts."
        )
    service = get_service(config.CREDENTIALS, config.TOKEN, config.SCOPES)
    today = datetime.now()
    for idx, r in targets.iterrows():
        try:
            msg = build_message(
                r["Public_Email"],
                r["Personalized_Email_Subject"],
                r["Generated_Email_Body"],
                config.CV_FILE,
            )
            if do_send:
                result = send_message(service, msg)
                df.at[idx, "Email_Status"] = "Sent"
                df.at[idx, "Gmail_Message_ID"] = result.get("id", "")
                df.at[idx, "Date_Contacted"] = today.strftime("%Y-%m-%d")
                df.at[idx, "Follow_Up_Date"] = (
                    today + timedelta(days=config.FOLLOW_UP_DAYS)
                ).strftime("%Y-%m-%d")
                print(f"SENT: {r['Professor']} <{r['Public_Email']}>")
            else:
                result = create_draft(service, msg)
                df.at[idx, "Email_Status"] = "Draft created"
                df.at[idx, "Gmail_Draft_ID"] = result.get("id", "")
                print(f"DRAFT: {r['Professor']} <{r['Public_Email']}> | {result.get('id', '')}")
            df.at[idx, "Last_Error"] = ""
            save_data(df)
        except Exception as e:
            df.at[idx, "Email_Status"] = "Error"
            df.at[idx, "Last_Error"] = str(e)[:500]
            save_data(df)
            print(f"ERROR: {r['Professor']} <{r['Public_Email']}>: {e}")
    return df


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def stats(df):
    print(f"Total records: {len(df)}")
    print(f"Valid public emails: {df['Public_Email'].apply(valid_email).sum()}")
    print("\nEmail status:")
    print(df["Email_Status"].replace("", "Not contacted").value_counts().to_string())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="China Master's 2027 professor outreach via Gmail API"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats")

    pv = sub.add_parser("preview")
    pv.add_argument("--count", type=int, default=5)

    en = sub.add_parser("enhance")
    en.add_argument("--count", type=int, default=config.DEFAULT_BATCH_SIZE,
                    help="Number of eligible professors to enhance")
    en.add_argument("--preview", action="store_true",
                    help="Show AI-enhanced emails without saving to CSV")

    dr = sub.add_parser("draft")
    dr.add_argument("--count", type=int, default=config.DEFAULT_BATCH_SIZE)

    se = sub.add_parser("send")
    se.add_argument("--count", type=int, default=1)

    args = p.parse_args()
    df = load_data()

    if args.cmd == "stats":
        stats(df)
    elif args.cmd == "preview":
        preview(df, args.count)
    elif args.cmd == "enhance":
        enhance(df, args.count, preview_only=args.preview)
    elif args.cmd == "draft":
        process(df, args.count, False)
    elif args.cmd == "send":
        process(df, args.count, True)


if __name__ == "__main__":
    main()
