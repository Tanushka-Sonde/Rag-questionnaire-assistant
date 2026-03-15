"""
Streamlit frontend for the RAG Questionnaire Assistant.
Run:  streamlit run app.py
"""

import streamlit as st
import requests, json, os

API = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="StreamHive QA Assistant", page_icon="🎬", layout="wide")

# ─── Session helpers ─────────────────────────────────────────────────────────

def token_headers():
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}

def api(method: str, path: str, **kwargs):
    fn = getattr(requests, method)
    r = fn(f"{API}{path}", headers=token_headers(), **kwargs)
    return r

# ─── Styling ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; letter-spacing: -0.5px; }

    .stApp { background: #0d0f14; color: #e8eaf0; }
    
    .answer-card {
        background: #151820;
        border: 1px solid #252836;
        border-left: 3px solid #4f8ef7;
        border-radius: 6px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }
    .q-label { color: #4f8ef7; font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; }
    .q-text { font-weight: 600; font-size: 0.95rem; margin: 0.3rem 0 0.6rem; }
    .a-text { color: #c8cad6; line-height: 1.6; font-size: 0.9rem; }
    .citation-badge {
        display: inline-block;
        background: #1e2535;
        border: 1px solid #3a4260;
        border-radius: 3px;
        padding: 1px 8px;
        font-size: 0.75rem;
        color: #7fa8f5;
        font-family: 'IBM Plex Mono', monospace;
        margin: 2px;
    }
    .snippet { color: #6b7280; font-size: 0.8rem; font-style: italic; border-left: 2px solid #3a4260; padding-left: 8px; margin-top: 4px; }
    .metric-box { background: #151820; border: 1px solid #252836; border-radius: 8px; padding: 1rem; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ─── Auth pages ──────────────────────────────────────────────────────────────

def login_page():
    st.title("🎬 StreamHive QA Assistant")
    st.caption("Automated questionnaire answering powered by RAG")

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        username = st.text_input("Username", key="li_user")
        password = st.text_input("Password", type="password", key="li_pass")
        if st.button("Log In", use_container_width=True):
            r = requests.post(f"{API}/auth/login", data={"username": username, "password": password})
            if r.ok:
                st.session_state["token"] = r.json()["access_token"]
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab_signup:
        email    = st.text_input("Email", key="su_email")
        username = st.text_input("Username", key="su_user")
        password = st.text_input("Password", type="password", key="su_pass")
        if st.button("Create Account", use_container_width=True):
            r = requests.post(f"{API}/auth/signup", json={"email": email, "username": username, "password": password})
            if r.ok:
                st.success("Account created! Please log in.")
            else:
                try:
                    st.error(r.json().get("detail", "Error"))
                except Exception:
                    st.error(f"Error {r.status_code}: {r.text}")


# ─── Main app ────────────────────────────────────────────────────────────────

def main_app():
    with st.sidebar:
        st.markdown(f"### 🎬 StreamHive QA")
        st.caption(f"Logged in as **{st.session_state.get('username')}**")
        st.divider()
        page = st.radio("Navigate", ["📄 New Run", "📋 My Runs", "📚 Reference Docs"])
        st.divider()
        if st.button("Log Out"):
            st.session_state.clear()
            st.rerun()

    if page == "📄 New Run":
        new_run_page()
    elif page == "📋 My Runs":
        my_runs_page()
    else:
        reference_docs_page()


# ─── Pages ───────────────────────────────────────────────────────────────────

def new_run_page():
    st.title("📄 New Questionnaire Run")

    col1, col2 = st.columns([2, 1])
    with col1:
        run_name = st.text_input("Run Name", value="Security Assessment Q1 2025")
        q_file   = st.file_uploader("Upload Questionnaire (.csv / .txt / .pdf)", type=["csv", "txt", "pdf"])

    with col2:
        st.markdown("**Quick Tips**")
        st.markdown("- CSV: columns `question_id`, `question`")
        st.markdown("- TXT: one question per line")
        st.markdown("- PDF: questions extracted automatically")

    if q_file and st.button("🚀 Create Run & Generate Answers", use_container_width=True, type="primary"):
        with st.spinner("Uploading questionnaire…"):
            r = api("post", "/runs/create", files={"file": q_file}, data={"run_name": run_name})
        if not r.ok:
            st.error(r.text)
            return
        run = r.json()
        st.success(f"Run #{run['id']} created!")

        with st.spinner("Generating answers with AI… (this may take ~30 seconds)"):
            r2 = api("post", f"/runs/{run['id']}/generate")
        if not r2.ok:
            st.error(r2.text)
            return

        st.session_state["active_run_id"] = run["id"]
        st.session_state["active_answers"] = r2.json()
        st.success("✅ Answers generated! Scroll down to review.")
        render_answers(run["id"], r2.json())


def my_runs_page():
    st.title("📋 My Runs")
    r = api("get", "/runs")
    if not r.ok:
        st.error("Failed to load runs")
        return
    runs = r.json()
    if not runs:
        st.info("No runs yet. Create one in **New Run**.")
        return

    for run in runs:
        with st.expander(f"#{run['id']} — {run['name']}  |  {run['status'].upper()}  |  {run['created_at'][:10]}"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"View & Edit Answers", key=f"view_{run['id']}"):
                    r2 = api("get", f"/runs/{run['id']}/answers")
                    if r2.ok:
                        render_answers(run["id"], r2.json())
            with col2:
                dl = api("get", f"/runs/{run['id']}/export")
                if dl.ok:
                    st.download_button(
                        "📥 Export .docx",
                        data=dl.content,
                        file_name=f"run_{run['id']}_answers.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_{run['id']}"
                    )


def reference_docs_page():
    st.title("📚 Reference Documents")

    st.markdown("#### Upload New Reference Document")
    ref_file = st.file_uploader("Upload (.txt / .pdf / .md)", type=["txt", "pdf", "md"])
    if ref_file and st.button("📤 Upload & Index"):
        with st.spinner("Indexing…"):
            r = api("post", "/reference-docs/upload", files={"file": ref_file})
        if r.ok:
            st.success(r.json()["message"])
        else:
            st.error(r.text)

    st.divider()
    if st.button("⚡ Load Default StreamHive Reference Docs"):
        with st.spinner("Loading bundled docs…"):
            r = api("post", "/reference-docs/load-defaults")
        if r.ok:
            st.success(f"Loaded: {', '.join(r.json()['loaded'])}")
        else:
            st.error(r.text)

    st.markdown("#### Indexed Documents")
    r = api("get", "/reference-docs")
    if r.ok:
        docs = r.json()["docs"]
        if docs:
            for d in docs:
                st.markdown(f"✅ `{d}`")
        else:
            st.info("No documents indexed yet.")


# ─── Answer Renderer ─────────────────────────────────────────────────────────

def render_answers(run_id: int, answers: list):
    if not answers:
        st.warning("No answers found.")
        return

    # Coverage summary
    total   = len(answers)
    found   = sum(1 for a in answers if a["answer_text"] != "Not found in references.")
    missing = total - found
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Questions", total)
    c2.metric("Answered with Citations", found)
    c3.metric("Not Found", missing)

    st.divider()

    for ans in answers:
        citations = []
        try:
            citations = json.loads(ans["citations"]) if ans["citations"] else []
        except Exception:
            pass

        # Render card
        st.markdown(f"""
        <div class="answer-card">
            <div class="q-label">Question {ans['question_id']}</div>
            <div class="q-text">{ans['question_text']}</div>
            <div class="a-text">{ans['answer_text']}</div>
        </div>
        """, unsafe_allow_html=True)

        if citations:
            sources_html = "".join(f'<span class="citation-badge">📄 {c["source"]}</span>' for c in citations)
            st.markdown(sources_html, unsafe_allow_html=True)
            with st.expander("🔍 Evidence Snippets"):
                for c in citations:
                    st.markdown(f'<div class="snippet"><b>{c["source"]}</b><br>{c["snippet"]}…</div>', unsafe_allow_html=True)

        # Edit
        with st.expander("✏️ Edit Answer"):
            new_text = st.text_area("Edit answer:", value=ans["answer_text"], key=f"edit_{ans['id']}", height=100)
            if st.button("💾 Save", key=f"save_{ans['id']}"):
                r = api("patch", f"/answers/{ans['id']}", json={"answer_text": new_text})
                if r.ok:
                    st.success("Saved!")
                else:
                    st.error("Save failed")

    st.divider()
    # Export button
    dl = api("get", f"/runs/{run_id}/export")
    if dl.ok:
        st.download_button(
            "📥 Download Answers as .docx",
            data=dl.content,
            file_name=f"run_{run_id}_answers.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            type="primary"
        )


# ─── Entry point ─────────────────────────────────────────────────────────────

if "token" not in st.session_state:
    login_page()
else:
    main_app()