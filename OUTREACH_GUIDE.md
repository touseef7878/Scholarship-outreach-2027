# Outreach Run Guide — 10 Professors

Step-by-step commands for a complete outreach run: AI enhancement → preview → save → draft → (optional) send directly.

All commands assume you are in the project folder with the venv active.

---

## Before You Start

Make sure the virtual environment is set up and dependencies are installed:

```powershell
# From the project folder
.venv\Scripts\python.exe outreach.py stats
```

Expected output:
```
Total records: 64
Valid public emails: 62

Email status:
Not contacted    62
```

If you see errors, run:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Step 1 — Preview Current Emails (No AI, No Gmail)

Check the raw emails as they exist in the CSV before any AI enhancement:

```powershell
.venv\Scripts\python.exe outreach.py preview --count 10
```

This prints the next 10 eligible emails to your terminal.
Nothing is saved, nothing is sent. Use this to sanity-check professor names, emails, and subjects.

---

## Step 2 — Generate AI Hooks (Preview First)

Generate personalised opening hooks using Groq AI.
Use `--preview` flag first so you can read the output before committing:

```powershell
.venv\Scripts\python.exe outreach.py enhance --count 10 --preview
```

Each email will show:

```
================================================================================
TO      : professor@university.edu.cn
SUBJECT : Prospective Master's Student for 2027 – Computer Vision / AI Research
--------------------------------------------------------------------------------
Dear Professor [Name],

[2-3 sentence AI hook specific to this professor's research + your FYP]

My name is Touseef Ur Rehman, a BS Computer Science graduate...

I am preparing applications for fully funded Master's opportunities...

I have attached my academic CV...

Best regards,
Touseef Ur Rehman
...
================================================================================
```

Read every hook carefully. The AI hook should:
- Name the professor's actual research area
- Reference OceanGuard AI / YOLO26s naturally
- Feel human-written, not templated
- Be 2-3 complete sentences

If any hook looks off, just run `enhance --preview` again — it generates fresh output each time.

---

## Step 3 — Save AI Hooks to CSV

Once you are happy with the preview, save the enhanced emails to the database:

```powershell
.venv\Scripts\python.exe outreach.py enhance --count 10
```

Output:
```
Enhancing: Yixiong Liang <yxliang@csu.edu.cn> ... done
Enhancing: Shu Liu <sliu35@csu.edu.cn> ... done
Enhancing: Jin Yuan <yuanjin@hnu.edu.cn> ... done
...
```

This updates `Generated_Email_Body` and `Professor_Specific_Opening` in the CSV for each professor.
The CSV is checkpointed after every professor — a crash will not lose completed work.

---

## Step 4 — Create Gmail Drafts

Create 10 Gmail drafts. Each draft has the professor's email, personalised subject, full email body, and your CV attached.

```powershell
.venv\Scripts\python.exe outreach.py draft --count 10
```

Output:
```
DRAFT: Yixiong Liang <yxliang@csu.edu.cn> | r-8702720563741131619
DRAFT: Shu Liu <sliu35@csu.edu.cn> | r2226739226906653410
...
```

- No browser login needed after the first run — `credentials/token.json` is reused automatically
- The CSV is updated to `Draft created` with the Gmail Draft ID for each professor
- Already drafted/sent professors are automatically skipped

---

## Step 5 — Review in Gmail

1. Open **Gmail → Drafts**
2. Open each of the 10 drafts
3. Verify:
   - Correct professor name in salutation
   - Correct university in the hook
   - Hook references their actual research
   - CV is attached (`Touseef_Ur_Rehman_Academic_CV.pdf`)
   - No placeholder text, no broken formatting

If anything looks wrong, edit it directly in Gmail before sending.

---

## Step 6A — Send from Gmail (Recommended)

Click **Send** inside Gmail for each draft you are happy with.

This is the safest approach — you have full control over each email before it leaves your account.

---

## Step 6B — Send Directly via Script (Optional)

If you want to send programmatically instead of clicking Send in Gmail, do the following:

**First — enable sending in `config.py`:**

Open `config.py` and change:
```python
ALLOW_SEND = False
```
to:
```python
ALLOW_SEND = True
```

**Then — send one at a time to start:**

```powershell
.venv\Scripts\python.exe outreach.py send --count 1
```

Check the sent message in Gmail. If it looks correct, send the rest:

```powershell
.venv\Scripts\python.exe outreach.py send --count 9
```

> ⚠️ Always start with `--count 1`. Never run `send` on the full dataset at once.
> Reset `ALLOW_SEND = False` in `config.py` when you are done sending.

---

## Step 7 — Confirm Final Stats

```powershell
.venv\Scripts\python.exe outreach.py stats
```

Expected after drafting 10:
```
Total records: 64
Valid public emails: 62

Email status:
Not contacted    52
Draft created    10
```

Expected after sending 10:
```
Total records: 64
Valid public emails: 62

Email status:
Not contacted    52
Sent             10
```

---

## Full Command Reference

```powershell
# Check current status
.venv\Scripts\python.exe outreach.py stats

# Preview next 10 emails from CSV (no AI, no Gmail)
.venv\Scripts\python.exe outreach.py preview --count 10

# Preview AI-enhanced emails without saving
.venv\Scripts\python.exe outreach.py enhance --count 10 --preview

# Save AI hooks to CSV
.venv\Scripts\python.exe outreach.py enhance --count 10

# Create 10 Gmail drafts
.venv\Scripts\python.exe outreach.py draft --count 10

# Send 1 email (ALLOW_SEND must be True in config.py)
.venv\Scripts\python.exe outreach.py send --count 1

# Send remaining (after testing with count 1)
.venv\Scripts\python.exe outreach.py send --count 9
```

---

## Repeat for Next Batch

After reviewing and sending the first 10, run the same sequence again for the next batch.
Already processed professors are automatically skipped — no duplicates.

```powershell
.venv\Scripts\python.exe outreach.py enhance --count 10 --preview
.venv\Scripts\python.exe outreach.py enhance --count 10
.venv\Scripts\python.exe outreach.py draft --count 10
```

You have **62 valid professor emails** in total. That is 6 batches of 10, plus 2 remaining.

---

## If Something Goes Wrong

**Hook truncated / retrying** — AI returned an incomplete sentence. The tool retries automatically 3 times. Just run `enhance` again if it keeps failing.

**Draft already exists in CSV but you deleted it from Gmail** — Reset those rows:
```powershell
.venv\Scripts\python.exe -c "
import pandas as pd
df = pd.read_csv('data/professors.csv', dtype=str).fillna('')
mask = df['Email_Status'].str.strip().str.lower() == 'draft created'
df.loc[mask, ['Email_Status', 'Gmail_Draft_ID']] = ''
df.to_csv('data/professors.csv', index=False, encoding='utf-8-sig')
print(f'Reset {mask.sum()} rows.')
"
```

**Token expired** — Delete `credentials/token.json` and run `draft` again. The browser will open for a fresh login.

**Error column in CSV** — Run `stats` and check the `Last_Error` column in the CSV for the affected professor row.
