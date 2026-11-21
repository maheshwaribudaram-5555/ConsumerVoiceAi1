"""ConsumerVoice AI - AI-Assisted Consumer Grievance Drafting and Legal Mapping System"""
import datetime as dt

import streamlit as st

from agents import Agent, Pipeline, css, llm, load_json, save_json, settings_sidebar, show_trace

st.set_page_config(page_title="ConsumerVoice AI", page_icon="📣", layout="wide")
css("""
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Work+Sans:wght@400;600&display=swap');
html, body, [class*="css"] { font-family:'Work Sans',sans-serif }
.stepper { display:flex; gap:0; margin:6px 0 16px } .stepper div { flex:1; text-align:center; padding:8px 4px; font-size:.85rem; border-bottom:4px solid #e7d9dc; color:#9b8a8e }
.stepper div.on { border-color:#7b2d3b; color:#7b2d3b; font-weight:600 } .stepper div.done { border-color:#c68b96; color:#7b2d3b }
.letter { background:#fffdf8; border:1px solid #e4dccf; box-shadow:0 2px 10px #0000000d; padding:30px 38px; font-family:'Merriweather',serif; font-size:.92rem; line-height:1.7; white-space:pre-wrap }
.ladder { border-left:3px solid #7b2d3b; padding-left:16px; margin-left:8px } .ladder .s { position:relative; margin-bottom:14px } .ladder .s:before { content:''; position:absolute; left:-24px; top:4px; width:13px; height:13px; border-radius:50%; background:#7b2d3b }
.ladder .s.f:before { background:#fff; border:2px solid #7b2d3b }
""")

ISSUES = {"Defective product": "replacement or full refund", "Service not provided": "refund of the amount paid", "Online delivery not received": "refund or immediate delivery",
          "Overcharging / MRP violation": "refund of the excess amount charged", "Warranty claim rejected": "repair or replacement under warranty", "Bank / UPI failed transaction": "reversal of the debited amount"}
STEPS = ["What happened", "Seller details", "Evidence", "Your letter", "Escalation"]

if "cv" not in st.session_state:
    st.session_state.cv = {"step": 0, "issue": "Defective product", "product": "Washing machine (front load, 7 kg)", "amount": 32490, "date": dt.date.today() - dt.timedelta(days=24),
                           "story": "The machine stopped spinning within 10 days. Technician visited twice but the problem continues. Service centre is now refusing replacement.",
                           "name": "Lakshmi Prasanna", "city": "Hyderabad", "seller": "ABC Electronics Pvt. Ltd.", "order": "INV-58213", "contacted": True, "evidence": ["Invoice / bill", "Warranty card", "Photos / videos"]}
S = st.session_state.cv
cases = load_json("cases.json", [])
st.sidebar.markdown("## 📣 ConsumerVoice")
st.sidebar.caption("Saved complaints: %d" % len(cases))
for c in cases[-5:]:
    st.sidebar.markdown("- %s · %s" % (c["product"], c["date"]))
settings_sidebar()
st.markdown("## 📣 ConsumerVoice AI")
st.markdown("<div class='stepper'>%s</div>" % "".join("<div class='%s'>%d. %s</div>" % ("on" if i == S["step"] else "done" if i < S["step"] else "", i + 1, n) for i, n in enumerate(STEPS)), unsafe_allow_html=True)


def _mv(d):
    st.session_state.cv["step"] += d


def nav(back=True, nxt="Next →"):
    c = st.columns([1, 1, 5])
    if back:
        c[0].button("← Back", key="bk%d" % S["step"], on_click=_mv, args=(-1,))
    if nxt:
        c[1].button(nxt, type="primary", key="nx%d" % S["step"], on_click=_mv, args=(1,))


def classifier(ctx):
    ctx["remedy"] = ISSUES[S["issue"]]
    days = (dt.date.today() - S["date"]).days
    ctx["days"] = days
    ctx["limit_ok"] = days <= 730
    return "Issue: %s → seek %s. %d days since purchase (limit 2 years)." % (S["issue"], ctx["remedy"], days)


def evidence(ctx):
    need = ["Invoice / bill", "Warranty card", "Photos / videos", "Emails / chat with seller", "Payment proof"]
    ctx["missing"] = [n for n in need if n not in S["evidence"]]
    ctx["strength"] = int(100 * (len(S["evidence"]) + (1 if S["contacted"] else 0)) / (len(need) + 1))
    return "Case strength %d%%; missing: %s." % (ctx["strength"], ", ".join(ctx["missing"]) or "none")


def drafter(ctx):
    body = llm("Write a formal consumer complaint body (4 short paragraphs) about: %s. Product %s, Rs. %d, bought %s. Seek %s." % (S["story"], S["product"], S["amount"], S["date"], ctx["remedy"]),
               "You draft polite, firm consumer complaint letters for Indian consumers.", 170)
    body = body or ("I purchased a %s from you on %s (Invoice/Order No. %s) for Rs. %s.\n\n%s\n\nThis amounts to a deficiency in service and an unfair trade practice under the Consumer Protection Act, 2019. "
                    "Despite my earlier requests, the issue has not been resolved.\n\nI therefore request you to provide %s within 15 days of receiving this letter, failing which I shall be constrained to approach the "
                    "National Consumer Helpline and the District Consumer Disputes Redressal Commission, at your cost and risk." %
                    (S["product"], S["date"].strftime("%d-%m-%Y"), S["order"], format(S["amount"], ","), S["story"], ctx["remedy"]))
    ctx["letter"] = "To\nThe Customer Care / Grievance Officer\n%s\n\nDate: %s\n\nSubject: Complaint regarding %s - %s\n\nDear Sir/Madam,\n\n%s\n\nEnclosures: %s\n\nYours faithfully,\n%s\n%s" % (
        S["seller"], dt.date.today().strftime("%d-%m-%Y"), S["issue"].lower(), S["product"], body, ", ".join(S["evidence"]) or "-", S["name"], S["city"])
    return "Formal notice drafted (%d words)." % len(ctx["letter"].split())


def escalation(ctx):
    d = dt.date.today()
    forum = "District Commission" if S["amount"] <= 5000000 else "State Commission"
    ctx["ladder"] = [("Day 0", "Send this letter to the seller by email / registered post", d), ("Day 15", "If no reply: register on National Consumer Helpline (1915 / consumerhelpline.gov.in)", d + dt.timedelta(days=15)),
                     ("Day 45", "If unresolved: file online on e-Daakhil before the %s" % forum, d + dt.timedelta(days=45)), ("Hearing", "Attend hearing with original documents", None)]
    return "4-stage escalation plan; forum: %s." % forum


R = Pipeline([Agent("Issue Classifier", "Identifies the grievance type and remedy", classifier, "🧭"), Agent("Evidence Checker", "Checks documents and case strength", evidence, "📎"),
              Agent("Letter Drafter", "Writes the formal complaint notice", drafter, "✍️"), Agent("Escalation Planner", "Plans helpline and commission steps", escalation, "🪜")]).run({}, show=False)

step = S["step"]
if step == 0:
    a, b = st.columns(2)
    S["issue"] = a.selectbox("Type of problem", list(ISSUES), index=list(ISSUES).index(S["issue"]))
    S["product"] = a.text_input("Product / service", S["product"])
    S["amount"] = a.number_input("Amount paid (Rs.)", 1, 100000000, S["amount"], step=500)
    S["date"] = a.date_input("Date of purchase", S["date"])
    S["story"] = b.text_area("Describe what went wrong", S["story"], height=210)
    nav(back=False)
elif step == 1:
    a, b = st.columns(2)
    S["name"] = a.text_input("Your name", S["name"])
    S["city"] = a.text_input("Your city", S["city"])
    S["seller"] = b.text_input("Seller / company name", S["seller"])
    S["order"] = b.text_input("Invoice / order number", S["order"])
    S["contacted"] = st.checkbox("I have already contacted the seller once", S["contacted"])
    nav()
elif step == 2:
    S["evidence"] = st.multiselect("Documents you have", ["Invoice / bill", "Warranty card", "Photos / videos", "Emails / chat with seller", "Payment proof"], S["evidence"])
    a, b = st.columns([1, 2])
    a.metric("Case strength", "%d%%" % R["strength"])
    a.progress(R["strength"] / 100)
    with b:
        if R["missing"]:
            st.warning("Try to collect: " + ", ".join(R["missing"]))
        if not R["limit_ok"]:
            st.error("More than 2 years since purchase - the commission may not admit the case without a delay explanation.")
        else:
            st.success("Within the 2-year limitation period (%d days since purchase)." % R["days"])
    nav(nxt="Draft my letter →")
elif step == 3:
    a, b = st.columns([3, 2], gap="large")
    a.markdown("<div class='letter'>%s</div>" % R["letter"], unsafe_allow_html=True)
    with b:
        st.markdown("**Remedy sought:** %s" % R["remedy"])
        st.download_button("⬇️ Download letter", R["letter"], "complaint_letter.txt")
        if st.button("💾 Save complaint"):
            cases.append({"product": S["product"], "seller": S["seller"], "amount": S["amount"], "date": dt.date.today().isoformat()})
            save_json("cases.json", cases); st.success("Saved to your complaints list.")
    nav(nxt="Plan escalation →")
else:
    st.markdown("<div class='ladder'>%s</div>" % "".join("<div class='s%s'><b>%s</b> - %s%s</div>" % ("" if i == 0 else " f", t, x, " <small>(by %s)</small>" % d.strftime("%d %b %Y") if d else "") for i, (t, x, d) in enumerate(R["ladder"])), unsafe_allow_html=True)
    st.info("No lawyer is needed at the District Commission. Filing fee is nil for claims up to Rs. 5 lakh.")
    nav(nxt=None)
    st.button("Start a new complaint", key="restart", on_click=lambda: st.session_state.pop("cv", None))
show_trace(R["trace"])
